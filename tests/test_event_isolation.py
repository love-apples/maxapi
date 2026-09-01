"""Тесты изоляции обработки событий (issue #198).

Проверяют, что при конкурентной обработке апдейтов одного
пользователя включённая изоляция сериализует ``handle()`` и
одноразовый шаг FSM выполняется ровно один раз.
"""

import asyncio

from maxapi.context import (
    DisabledEventIsolation,
    RedisEventIsolation,
    SimpleEventIsolation,
    State,
    StatesGroup,
)
from maxapi.dispatcher import Dispatcher
from maxapi.filters.state import StateFilter

from tests.conftest import setup_dispatcher_for_handle as _setup_for_handle


class Form(StatesGroup):
    waiting_amount = State()


def _one_shot_dispatcher(bot, isolation=None):
    """Диспетчер с одноразовым FSM-хендлером из issue #198.

    Returns:
        Кортеж (dispatcher, calls) — список вызовов хендлера.
    """
    kwargs = {}
    if isolation is not None:
        kwargs["event_isolation"] = isolation
    dp = Dispatcher(**kwargs)
    calls = []

    @dp.message_created(StateFilter(Form.waiting_amount))
    async def on_amount(event, context):
        calls.append(event)
        # Точка переключения, как do_transfer() в issue
        await asyncio.sleep(0.01)
        await context.set_state(None)

    _setup_for_handle(dp, bot)
    return dp, calls


class TestSimpleEventIsolation:
    """Тесты SimpleEventIsolation."""

    async def test_fsm_one_shot_executes_once(
        self, bot, fixture_message_created
    ):
        """Гонка из issue #198: два конкурентных апдейта одного
        пользователя в одноразовом FSM-шаге → хендлер выполняется
        ровно один раз."""
        dp, calls = _one_shot_dispatcher(bot, SimpleEventIsolation())

        chat_id, user_id = fixture_message_created.get_ids()
        await dp.fsm.set_state(
            chat_id=chat_id,
            user_id=user_id,
            state=Form.waiting_amount,
        )

        second = fixture_message_created.model_copy(deep=True)
        await asyncio.gather(
            dp.handle(fixture_message_created),
            dp.handle(second),
        )

        assert len(calls) == 1

    async def test_same_user_is_serialized_in_order(
        self, bot, fixture_message_created
    ):
        """Обработка апдейтов одного пользователя не перекрывается
        и идёт в порядке поступления."""
        dp = Dispatcher(event_isolation=SimpleEventIsolation())
        events_log = []

        @dp.message_created()
        async def handler(event):
            events_log.append("start")
            await asyncio.sleep(0.01)
            events_log.append("end")

        _setup_for_handle(dp, bot)

        second = fixture_message_created.model_copy(deep=True)
        await asyncio.gather(
            dp.handle(fixture_message_created),
            dp.handle(second),
        )

        assert events_log == ["start", "end", "start", "end"]

    async def test_different_users_run_concurrently(
        self, bot, fixture_message_created
    ):
        """Апдейты разных пользователей не блокируют друг друга."""
        dp = Dispatcher(event_isolation=SimpleEventIsolation())
        arrived = set()
        completed = []
        both_arrived = asyncio.Event()

        @dp.message_created()
        async def handler(event):
            user_id = event.get_ids()[1]
            arrived.add(user_id)
            if len(arrived) == 2:
                both_arrived.set()
            # Ждём, пока оба хендлера войдут в критическую секцию:
            # при (ошибочной) сериализации первый упрётся в таймаут
            await asyncio.wait_for(both_arrived.wait(), timeout=1.0)
            completed.append(user_id)

        _setup_for_handle(dp, bot)

        second = fixture_message_created.model_copy(deep=True)
        second.message.sender.user_id = (
            fixture_message_created.message.sender.user_id + 1
        )
        await asyncio.gather(
            dp.handle(fixture_message_created),
            dp.handle(second),
        )

        assert len(completed) == 2

    async def test_locks_are_cleaned_up(self, bot, fixture_message_created):
        """Неиспользуемые блокировки удаляются из словаря."""
        isolation = SimpleEventIsolation()
        dp, _ = _one_shot_dispatcher(bot, isolation)

        second = fixture_message_created.model_copy(deep=True)
        await asyncio.gather(
            dp.handle(fixture_message_created),
            dp.handle(second),
        )

        assert isolation._locks == {}
        assert isolation._refcounts == {}

    async def test_close_clears_locks(self):
        """close() очищает словарь блокировок."""
        isolation = SimpleEventIsolation()
        async with isolation.lock((1, 2)):
            assert (1, 2) in isolation._locks
        await isolation.close()
        assert isolation._locks == {}
        assert isolation._refcounts == {}


class TestDisabledEventIsolation:
    """Тесты поведения по умолчанию (изоляция отключена)."""

    async def test_default_isolation_is_disabled(self):
        """По умолчанию Dispatcher использует DisabledEventIsolation."""
        dp = Dispatcher()
        assert isinstance(dp.event_isolation, DisabledEventIsolation)

    async def test_race_still_possible_without_isolation(
        self, bot, fixture_message_created
    ):
        """Без изоляции гонка из issue #198 воспроизводится:
        одноразовый хендлер выполняется дважды (документация
        opt-in-поведения)."""
        dp, calls = _one_shot_dispatcher(bot)

        chat_id, user_id = fixture_message_created.get_ids()
        await dp.fsm.set_state(
            chat_id=chat_id,
            user_id=user_id,
            state=Form.waiting_amount,
        )

        second = fixture_message_created.model_copy(deep=True)
        await asyncio.gather(
            dp.handle(fixture_message_created),
            dp.handle(second),
        )

        assert len(calls) == 2

    async def test_lock_is_noop(self):
        """lock() отключённой изоляции ничего не блокирует."""
        isolation = DisabledEventIsolation()
        async with isolation.lock((1, 2)), isolation.lock((1, 2)):
            pass
        await isolation.close()


class _FakeRedisLock:
    """Имитация redis.asyncio.lock.Lock (acquire/release)."""

    def __init__(self, log: list, release_error: Exception | None = None):
        self._log = log
        self._release_error = release_error

    async def acquire(self) -> bool:
        self._log.append("acquired")
        return True

    async def release(self) -> None:
        if self._release_error is not None:
            raise self._release_error
        self._log.append("released")


class _FakeRedis:
    """Имитация redis.asyncio.Redis для проверки lock()."""

    def __init__(self, release_error: Exception | None = None) -> None:
        self.calls: list[tuple] = []
        self.log: list[str] = []
        self._release_error = release_error

    def lock(self, name, timeout, sleep):
        self.calls.append((name, timeout, sleep))
        return _FakeRedisLock(self.log, self._release_error)


class TestRedisEventIsolation:
    """Тесты RedisEventIsolation."""

    async def test_lock_uses_redis_lock_with_prefixed_key(self):
        """lock() строит ключ в схеме RedisContext и передаёт
        настройки блокировки."""
        redis = _FakeRedis()
        isolation = RedisEventIsolation(
            redis,
            key_prefix="pfx",
            lock_timeout=30,
            lock_sleep=0.2,
        )

        async with isolation.lock((10, 20)):
            assert redis.log == ["acquired"]

        assert redis.calls == [("pfx:10:20:lock", 30, 0.2)]
        assert redis.log == ["acquired", "released"]
        await isolation.close()

    async def test_defaults(self):
        """Дефолтные параметры блокировки."""
        redis = _FakeRedis()
        isolation = RedisEventIsolation(redis)

        async with isolation.lock((None, 5)):
            pass

        name, timeout, sleep = redis.calls[0]
        assert name == "maxapi:None:5:lock"
        assert timeout == 60.0
        assert sleep == 0.1

    async def test_release_error_is_swallowed(self):
        """Ошибка release (например, LockNotOwnedError после
        истечения lock_timeout) не превращает успешно обработанное
        событие в ошибку."""
        redis = _FakeRedis(release_error=RuntimeError("lock expired"))
        isolation = RedisEventIsolation(redis)
        entered = []

        async with isolation.lock((1, 2)):
            entered.append(True)

        assert entered == [True]
        assert redis.log == ["acquired"]


class TestStopPollingClosesIsolation:
    """Тесты жизненного цикла изоляции."""

    async def test_stop_polling_closes_isolation(self):
        """stop_polling() освобождает ресурсы изоляции."""
        isolation = SimpleEventIsolation()
        isolation._locks[(1, 2)] = asyncio.Lock()
        isolation._refcounts[(1, 2)] = 0

        dp = Dispatcher(event_isolation=isolation)
        await dp.stop_polling()

        assert isolation._locks == {}
        assert isolation._refcounts == {}
