"""Тесты остановки polling: stop_polling дожидается цикла (#217)."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from maxapi.bot import Bot
from maxapi.context import SimpleEventIsolation
from maxapi.dispatcher import Dispatcher
from maxapi.exceptions.max import InvalidToken, MaxApiError, MaxConnection
from maxapi.filters.command import Command, CommandsInfo
from maxapi.types.updates.message_created import MessageCreated

# Все ожидания в тестах укладываются в этот таймаут: паузы диспетчера
# (30 и 5 секунд) должны прерываться остановкой, а не истекать.
STOP_TIMEOUT = 1


@pytest.fixture
def polling_bot(mock_bot_token):
    """Бот с замоканными сетевыми вызовами для polling-тестов."""
    bot = Bot(token=mock_bot_token, auto_check_subscriptions=False)
    bot.session = None
    bot.get_me = AsyncMock(
        return_value=Mock(username="tester", first_name="Tester", user_id=1)
    )
    bot.get_updates = AsyncMock(return_value={"updates": [], "marker": None})
    return bot


def _pending_tasks() -> set[asyncio.Task]:
    """Незавершённые задачи цикла событий, кроме текущей."""
    current = asyncio.current_task()
    return {task for task in asyncio.all_tasks() if task is not current}


@pytest.fixture(autouse=True)
async def _no_leaked_tasks():
    """Ни один тест файла не оставляет после себя висячих задач."""
    yield
    assert _pending_tasks() == set()


async def _let_tasks_run(iterations: int = 5) -> None:
    """Даёт другим задачам поработать, не завися от таймеров."""
    for _ in range(iterations):
        await asyncio.sleep(0)


def _reentrancy_warnings(caplog) -> list[str]:
    """Предупреждения shutdown о вызове из обработчика."""
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelname == "WARNING"
        and "shutdown вызван из" in record.getMessage()
    ]


class _CountingIsolation(SimpleEventIsolation):
    """Изоляция, считающая вызовы close()."""

    def __init__(self) -> None:
        super().__init__()
        self.closed = 0

    async def close(self) -> None:
        self.closed += 1
        await super().close()


def _hanging_updates(started: asyncio.Event, cancelled: list):
    """get_updates, который висит до отмены (эмуляция long polling)."""

    async def _get_updates(**kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        return {}

    return _get_updates


def _updates_once(batch: dict):
    """get_updates, который отдаёт пачку один раз, а затем висит."""
    calls = 0

    async def _get_updates(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return batch
        await asyncio.Event().wait()
        return batch

    return _get_updates


# ===========================================================================
# Прерывание висящего запроса и пауз между попытками
# ===========================================================================


class TestStopPollingInterrupts:
    """stop_polling прерывает сетевое ожидание и паузы."""

    async def test_pending_get_updates_is_cancelled(
        self, dispatcher, polling_bot
    ):
        """Висящий get_updates отменяется, цикл завершается быстро."""
        started = asyncio.Event()
        cancelled: list = []
        polling_bot.get_updates = _hanging_updates(started, cancelled)

        task = asyncio.create_task(dispatcher.start_polling(polling_bot))
        await asyncio.wait_for(started.wait(), STOP_TIMEOUT)

        await asyncio.wait_for(dispatcher.stop_polling(), STOP_TIMEOUT)

        assert task.done()
        assert cancelled == [True]
        assert dispatcher.polling is False
        assert dispatcher._polling_task is None

    @pytest.mark.parametrize(
        "error",
        [
            MaxConnection("нет связи"),
            MaxApiError(500, "ошибка API"),
            RuntimeError("неожиданная ошибка"),
        ],
        ids=["connection", "api", "unexpected"],
    )
    async def test_retry_pause_is_interrupted(
        self, dispatcher, polling_bot, error
    ):
        """Пауза после ошибки get_updates прерывается остановкой."""
        called = asyncio.Event()

        async def _get_updates(**kwargs):
            called.set()
            raise error

        polling_bot.get_updates = _get_updates

        task = asyncio.create_task(dispatcher.start_polling(polling_bot))
        await asyncio.wait_for(called.wait(), STOP_TIMEOUT)

        await asyncio.wait_for(dispatcher.stop_polling(), STOP_TIMEOUT)

        assert task.done()

    async def test_dispatch_error_pause_is_interrupted(
        self, dispatcher, polling_bot
    ):
        """Пауза после ошибки обработки пачки прерывается остановкой."""
        called = asyncio.Event()

        async def _get_updates(**kwargs):
            called.set()
            return {"updates": [], "marker": 1}

        polling_bot.get_updates = _get_updates

        with patch(
            "maxapi.dispatcher.process_update_request",
            new=AsyncMock(side_effect=RuntimeError("разбор упал")),
        ):
            task = asyncio.create_task(dispatcher.start_polling(polling_bot))
            await asyncio.wait_for(called.wait(), STOP_TIMEOUT)

            await asyncio.wait_for(dispatcher.stop_polling(), STOP_TIMEOUT)

        assert task.done()
        assert polling_bot.marker_updates is None

    async def test_sleep_without_stop_event_is_plain_sleep(self, dispatcher):
        """Вне polling пауза работает как обычный asyncio.sleep."""
        await dispatcher._sleep_unless_stopped(0)

    async def test_get_updates_or_stop_returns_none_if_already_stopped(
        self, dispatcher, polling_bot
    ):
        """Уже взведённый _stop_event: новый запрос не отправляется."""
        dispatcher._stop_event = asyncio.Event()
        dispatcher._stop_event.set()

        result = await dispatcher._get_updates_or_stop(polling_bot)

        assert result is None
        polling_bot.get_updates.assert_not_called()


# ===========================================================================
# Судьба пачки обновлений при остановке
# ===========================================================================


class TestStopPollingBatches:
    """Что происходит с уже полученными обновлениями."""

    async def test_batch_after_stop_is_not_dispatched(
        self, dispatcher, polling_bot
    ):
        """Пачка, пришедшая после остановки, не обрабатывается."""
        stops: list[asyncio.Task] = []

        async def _get_updates(**kwargs):
            # Остановка запрошена, пока запрос ещё в полёте: пачка
            # успевает вернуться, но диспетчеризовать её уже нельзя.
            stops.append(asyncio.create_task(dispatcher.stop_polling()))
            await asyncio.sleep(0)
            assert dispatcher.polling is False
            return {"updates": [], "marker": 99}

        polling_bot.get_updates = _get_updates
        dispatcher._dispatch_fetched_events = AsyncMock()

        task = asyncio.create_task(dispatcher.start_polling(polling_bot))
        await asyncio.wait_for(task, STOP_TIMEOUT)
        await asyncio.wait_for(asyncio.gather(*stops), STOP_TIMEOUT)

        assert dispatcher._dispatch_fetched_events.await_count == 0
        assert polling_bot.marker_updates is None
        assert dispatcher.polling is False

    async def test_inflight_batch_is_finished(
        self, dispatcher, polling_bot, fixture_message_created
    ):
        """Начатая до остановки пачка дорабатывается, маркер сдвигается."""
        entered = asyncio.Event()
        release = asyncio.Event()
        handled = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            entered.set()
            await release.wait()
            handled.append(event)

        polling_bot.get_updates = _updates_once({"updates": [], "marker": 77})

        with patch(
            "maxapi.dispatcher.process_update_request",
            new=AsyncMock(return_value=[fixture_message_created]),
        ):
            task = asyncio.create_task(dispatcher.start_polling(polling_bot))
            await asyncio.wait_for(entered.wait(), STOP_TIMEOUT)

            stop_task = asyncio.create_task(dispatcher.stop_polling())
            await asyncio.sleep(0)
            assert not stop_task.done()

            release.set()
            await asyncio.wait_for(stop_task, STOP_TIMEOUT)

        assert handled == [fixture_message_created]
        assert polling_bot.marker_updates == 77
        assert task.done()

    async def test_background_handlers_are_awaited(
        self, polling_bot, fixture_message_created
    ):
        """При use_create_task=True фоновые обработчики дожидаются."""
        dispatcher = Dispatcher(use_create_task=True)
        entered = asyncio.Event()
        release = asyncio.Event()
        handled = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            entered.set()
            await release.wait()
            handled.append(event)

        polling_bot.get_updates = _updates_once({"updates": [], "marker": 5})

        with patch(
            "maxapi.dispatcher.process_update_request",
            new=AsyncMock(return_value=[fixture_message_created]),
        ):
            task = asyncio.create_task(dispatcher.start_polling(polling_bot))
            await asyncio.wait_for(entered.wait(), STOP_TIMEOUT)

            stop_task = asyncio.create_task(dispatcher.stop_polling())
            await asyncio.sleep(0)
            assert not stop_task.done()

            release.set()
            await asyncio.wait_for(stop_task, STOP_TIMEOUT)

        assert handled == [fixture_message_created]
        assert dispatcher._background_tasks == set()
        assert task.done()


# ===========================================================================
# Вызовы stop_polling из обработчиков и в неожиданном порядке
# ===========================================================================


class TestStopPollingSafety:
    """stop_polling безопасен при любом порядке вызовов."""

    async def test_stop_from_inline_handler(
        self, dispatcher, polling_bot, fixture_message_created
    ):
        """Инлайн-обработчик может сам остановить polling."""
        handled = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            await dispatcher.stop_polling()
            handled.append(event)

        polling_bot.get_updates = _updates_once({"updates": [], "marker": 3})

        with patch(
            "maxapi.dispatcher.process_update_request",
            new=AsyncMock(return_value=[fixture_message_created]),
        ):
            await asyncio.wait_for(
                dispatcher.start_polling(polling_bot), STOP_TIMEOUT
            )

        assert handled == [fixture_message_created]
        assert polling_bot.marker_updates == 3
        assert dispatcher.polling is False
        assert dispatcher._polling_task is None

    async def test_stop_from_background_handler(
        self, polling_bot, fixture_message_created
    ):
        """Фоновый обработчик может сам остановить polling."""
        dispatcher = Dispatcher(use_create_task=True)
        handled = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            await dispatcher.stop_polling()
            handled.append(event)

        polling_bot.get_updates = _updates_once({"updates": [], "marker": 4})

        with patch(
            "maxapi.dispatcher.process_update_request",
            new=AsyncMock(return_value=[fixture_message_created]),
        ):
            task = asyncio.create_task(dispatcher.start_polling(polling_bot))
            await asyncio.wait_for(task, STOP_TIMEOUT)

            # Сам обработчик доживает в фоне: он дожидался цикла polling,
            # а не наоборот (иначе задача ждала бы саму себя).
            await asyncio.wait_for(
                asyncio.gather(*dispatcher._background_tasks), STOP_TIMEOUT
            )

        assert handled == [fixture_message_created]
        assert dispatcher._background_tasks == set()

    async def test_stop_from_background_handler_under_isolation(
        self, polling_bot, fixture_message_created
    ):
        """stop_polling() из обработчика под изоляцией не даёт дедлок.

        Второй апдейт того же пользователя ждёт блокировку, которую
        держит первый обработчик. Если бы shutdown() дренировал фон
        из-под обработчика, он ждал бы сам себя.
        """
        dispatcher = Dispatcher(
            use_create_task=True, event_isolation=SimpleEventIsolation()
        )
        handled: list[str] = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            if handled:
                handled.append("второй")
                return
            handled.append("первый")
            await dispatcher.stop_polling()

        polling_bot.get_updates = _updates_once({"updates": [], "marker": 9})

        with patch(
            "maxapi.dispatcher.process_update_request",
            new=AsyncMock(
                return_value=[
                    fixture_message_created,
                    fixture_message_created,
                ]
            ),
        ):
            task = asyncio.create_task(dispatcher.start_polling(polling_bot))
            await asyncio.wait_for(task, STOP_TIMEOUT)

            await asyncio.wait_for(
                asyncio.gather(*dispatcher._background_tasks), STOP_TIMEOUT
            )

        # Изоляция не сломана: второй обработчик дождался первого.
        assert handled == ["первый", "второй"]
        assert dispatcher._background_tasks == set()

    async def test_stop_without_start(self, dispatcher):
        """stop_polling без запуска polling не падает."""
        await asyncio.wait_for(dispatcher.stop_polling(), STOP_TIMEOUT)

        assert dispatcher.polling is False

    async def test_stop_twice(self, dispatcher, polling_bot):
        """Повторный stop_polling не падает."""
        started = asyncio.Event()
        polling_bot.get_updates = _hanging_updates(started, [])

        task = asyncio.create_task(dispatcher.start_polling(polling_bot))
        await asyncio.wait_for(started.wait(), STOP_TIMEOUT)

        await asyncio.wait_for(dispatcher.stop_polling(), STOP_TIMEOUT)
        await asyncio.wait_for(dispatcher.stop_polling(), STOP_TIMEOUT)

        assert task.done()

    async def test_concurrent_stops(self, dispatcher, polling_bot):
        """Конкурентные stop_polling завершаются оба."""
        started = asyncio.Event()
        polling_bot.get_updates = _hanging_updates(started, [])

        task = asyncio.create_task(dispatcher.start_polling(polling_bot))
        await asyncio.wait_for(started.wait(), STOP_TIMEOUT)

        await asyncio.wait_for(
            asyncio.gather(
                dispatcher.stop_polling(), dispatcher.stop_polling()
            ),
            STOP_TIMEOUT,
        )

        assert task.done()

    async def test_restart_after_stop(self, dispatcher, polling_bot):
        """После остановки polling можно запустить заново."""
        stop_events = []

        @dispatcher.message_created(Command("ping"))
        async def _handler(event: MessageCreated):
            """Обработчик команды.

            commands_info: Проверка связи
            """

        for _ in range(2):
            started = asyncio.Event()
            polling_bot.get_updates = _hanging_updates(started, [])

            task = asyncio.create_task(dispatcher.start_polling(polling_bot))
            await asyncio.wait_for(started.wait(), STOP_TIMEOUT)
            stop_events.append(dispatcher._stop_event)

            # Запущенный заново диспетчер не «закрывается» и не
            # накапливает команды от прошлой подготовки.
            assert dispatcher._closing is False
            assert polling_bot.commands == [
                CommandsInfo(commands=["ping"], info="Проверка связи")
            ]

            await asyncio.wait_for(dispatcher.stop_polling(), STOP_TIMEOUT)

            assert task.done()

        assert stop_events[0] is not stop_events[1]

    async def test_second_start_polling_is_rejected(
        self, dispatcher, polling_bot
    ):
        """Повторный start_polling на живом диспетчере — RuntimeError."""
        started = asyncio.Event()
        polling_bot.get_updates = _hanging_updates(started, [])

        task = asyncio.create_task(dispatcher.start_polling(polling_bot))
        await asyncio.wait_for(started.wait(), STOP_TIMEOUT)

        with pytest.raises(RuntimeError, match="Polling уже запущен"):
            await dispatcher.start_polling(polling_bot)

        await asyncio.wait_for(dispatcher.stop_polling(), STOP_TIMEOUT)

        assert task.done()

    async def test_stop_during_on_started_allows_full_restart(
        self, dispatcher, polling_bot
    ):
        """Остановка во время on_started не съедает подготовку рестарта."""
        entered = asyncio.Event()
        release = asyncio.Event()
        starts: list[str] = []

        @dispatcher.on_started()
        async def _on_started():
            starts.append("on_started")
            entered.set()
            await release.wait()

        task = asyncio.create_task(dispatcher.start_polling(polling_bot))
        await asyncio.wait_for(entered.wait(), STOP_TIMEOUT)

        stop_task = asyncio.create_task(dispatcher.stop_polling())
        await asyncio.sleep(0)
        release.set()
        await asyncio.wait_for(stop_task, STOP_TIMEOUT)

        assert task.done()
        assert dispatcher._ready is False

        # Повторный запуск снова проходит подготовку целиком.
        started = asyncio.Event()
        polling_bot.get_updates = _hanging_updates(started, [])

        task = asyncio.create_task(dispatcher.start_polling(polling_bot))
        await asyncio.wait_for(started.wait(), STOP_TIMEOUT)
        await asyncio.wait_for(dispatcher.stop_polling(), STOP_TIMEOUT)

        assert task.done()
        assert starts == ["on_started", "on_started"]
        assert polling_bot.get_me.await_count == 2

    async def test_stop_from_on_started_allows_full_restart(
        self, dispatcher, polling_bot
    ):
        """Остановка прямо из on_started не съедает подготовку рестарта."""
        starts: list[str] = []

        @dispatcher.on_started()
        async def _on_started():
            starts.append("on_started")
            if len(starts) == 1:
                await dispatcher.stop_polling()

        await asyncio.wait_for(
            dispatcher.start_polling(polling_bot), STOP_TIMEOUT
        )

        assert dispatcher._ready is False

        # Повторный запуск снова проходит подготовку целиком.
        started = asyncio.Event()
        polling_bot.get_updates = _hanging_updates(started, [])

        task = asyncio.create_task(dispatcher.start_polling(polling_bot))
        await asyncio.wait_for(started.wait(), STOP_TIMEOUT)
        await asyncio.wait_for(dispatcher.stop_polling(), STOP_TIMEOUT)

        assert task.done()
        assert starts == ["on_started", "on_started"]
        assert polling_bot.get_me.await_count == 2

    async def test_restart_after_shutdown_resets_closing(
        self, dispatcher, polling_bot, fixture_message_created, caplog
    ):
        """startup → shutdown → startup: диспетчер снова принимает события."""
        await dispatcher.startup(polling_bot)
        await dispatcher.shutdown()

        assert dispatcher._closing is True

        await dispatcher.startup(polling_bot)

        assert dispatcher._closing is False

        with caplog.at_level("WARNING", logger="dispatcher"):
            await asyncio.wait_for(
                dispatcher.spawn_handle_task(fixture_message_created),
                STOP_TIMEOUT,
            )

        assert not any(
            "во время shutdown" in record.getMessage()
            for record in caplog.records
        )

    async def test_spawn_handle_task_warns_when_closing(
        self, dispatcher, polling_bot, fixture_message_created, caplog
    ):
        """spawn_handle_task() после shutdown() без рестарта предупреждает."""
        await dispatcher.startup(polling_bot)
        await dispatcher.shutdown()

        assert dispatcher._closing is True

        with caplog.at_level("WARNING", logger="dispatcher"):
            await asyncio.wait_for(
                dispatcher.spawn_handle_task(fixture_message_created),
                STOP_TIMEOUT,
            )

        assert any(
            "во время shutdown" in record.getMessage()
            for record in caplog.records
        )


# ===========================================================================
# Реентрантный shutdown
# ===========================================================================


class TestReentrantShutdown:
    """Что дренирует shutdown, вызванный из обработчика."""

    async def test_stop_in_spawned_task_drains_background(
        self, polling_bot, fixture_message_created, caplog
    ):
        """stop_polling() в отдельной задаче дренирует фон полностью."""
        dispatcher = Dispatcher(use_create_task=True)
        release = asyncio.Event()
        requested = asyncio.Event()
        handled: list[str] = []
        stops: list[asyncio.Task] = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            # Задача наследует контекст обработчика, но диспетчеру не
            # принадлежит — вызов из неё не реентрантный.
            stops.append(asyncio.create_task(dispatcher.stop_polling()))
            requested.set()
            await release.wait()
            handled.append("обработан")

        polling_bot.get_updates = _updates_once({"updates": [], "marker": 21})

        with (
            patch(
                "maxapi.dispatcher.process_update_request",
                new=AsyncMock(return_value=[fixture_message_created]),
            ),
            caplog.at_level("WARNING", logger="dispatcher"),
        ):
            task = asyncio.create_task(dispatcher.start_polling(polling_bot))
            await asyncio.wait_for(requested.wait(), STOP_TIMEOUT)
            await asyncio.wait_for(task, STOP_TIMEOUT)

            # Остановка не завершается, пока фоновый обработчик в работе.
            await _let_tasks_run()
            assert not stops[0].done()
            assert handled == []

            release.set()
            await asyncio.wait_for(stops[0], STOP_TIMEOUT)

        assert handled == ["обработан"]
        assert dispatcher._background_tasks == set()
        assert _reentrancy_warnings(caplog) == []

    async def test_shutdown_of_other_dispatcher_drains_it(
        self, polling_bot, fixture_message_created
    ):
        """shutdown() чужого диспетчера из обработчика дренирует его фон."""
        first = Dispatcher(use_create_task=True)
        second = Dispatcher(use_create_task=True)
        release = asyncio.Event()
        order: list[str] = []

        @second.message_created()
        async def _second_handler(event: MessageCreated):
            await release.wait()
            order.append("второй")

        @first.message_created()
        async def _first_handler(event: MessageCreated):
            second.spawn_handle_task(event)
            await _let_tasks_run()
            # Задача обработчика принадлежит first, а не second:
            # для second вызов внешний и дренаж пропускать нельзя.
            await second.shutdown()
            order.append("первый")

        await first.startup(polling_bot)
        await second.startup(polling_bot)

        first_task = first.spawn_handle_task(fixture_message_created)
        await _let_tasks_run()

        assert order == []

        release.set()
        await asyncio.wait_for(first_task, STOP_TIMEOUT)

        assert order == ["второй", "первый"]
        assert second._background_tasks == set()

    async def test_inline_stop_drains_deferred(
        self, polling_bot, fixture_message_created, caplog
    ):
        """Инлайн-остановка дожидается фона и закрывает изоляцию."""
        isolation = _CountingIsolation()
        dispatcher = Dispatcher(event_isolation=isolation)
        handled: list[str] = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            if handled:
                handled.append("фоновый")
                return
            handled.append("инлайн")
            # «Вебхучная» задача поставлена до остановки и ждёт
            # блокировку изоляции, которую держит этот обработчик.
            dispatcher.spawn_handle_task(event)
            await dispatcher.stop_polling()

        polling_bot.get_updates = _updates_once({"updates": [], "marker": 31})

        with (
            patch(
                "maxapi.dispatcher.process_update_request",
                new=AsyncMock(return_value=[fixture_message_created]),
            ),
            caplog.at_level("WARNING", logger="dispatcher"),
        ):
            await asyncio.wait_for(
                dispatcher.start_polling(polling_bot), STOP_TIMEOUT
            )

        assert handled == ["инлайн", "фоновый"]
        assert dispatcher._background_tasks == set()
        assert isolation.closed == 1
        assert _reentrancy_warnings(caplog) == []

    async def test_background_stop_warns_about_skipped_drain(
        self, polling_bot, fixture_message_created, caplog
    ):
        """Из фонового обработчика дренаж пропускается — с warning.

        Счётчик в предупреждении не должен включать саму вызывающую
        задачу: пачка из двух событий порождает два фоновых
        обработчика, первый блокируется, второй зовёт stop_polling() —
        и warning должен назвать ровно одну «пропущенную» задачу
        (первую), а не две.
        """
        dispatcher = Dispatcher(use_create_task=True)
        started = asyncio.Event()
        release = asyncio.Event()
        handled: list[str] = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            if not handled:
                # Первая задача: блокируется, пока её не отпустят.
                handled.append("первый")
                started.set()
                await release.wait()
                handled.append("первый-продолжил")
                return
            # Вторая задача: дожидается первой и останавливает polling.
            await started.wait()
            await dispatcher.stop_polling()
            handled.append("второй-остановил")

        polling_bot.get_updates = _updates_once({"updates": [], "marker": 41})

        with (
            patch(
                "maxapi.dispatcher.process_update_request",
                new=AsyncMock(
                    return_value=[
                        fixture_message_created,
                        fixture_message_created,
                    ]
                ),
            ),
            caplog.at_level("WARNING", logger="dispatcher"),
        ):
            task = asyncio.create_task(dispatcher.start_polling(polling_bot))
            await asyncio.wait_for(started.wait(), STOP_TIMEOUT)
            await asyncio.wait_for(task, STOP_TIMEOUT)

            release.set()
            await asyncio.wait_for(
                asyncio.gather(*dispatcher._background_tasks), STOP_TIMEOUT
            )

        assert handled == ["первый", "второй-остановил", "первый-продолжил"]

        warnings = _reentrancy_warnings(caplog)
        assert len(warnings) == 1
        assert "(1)" in warnings[0]

    async def test_solo_background_stop_does_not_warn(
        self, polling_bot, fixture_message_created, caplog
    ):
        """Одиночный фоновый хендлер зовёт stop_polling() — без warning.

        Если вызывающая задача — единственная в пуле фоновых задач,
        дренировать (кроме неё самой) нечего: должен сработать debug,
        а не warning (покрывает ветку else в shutdown()).
        """
        dispatcher = Dispatcher(use_create_task=True)
        handled: list[str] = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            await dispatcher.stop_polling()
            handled.append("обработан")

        polling_bot.get_updates = _updates_once({"updates": [], "marker": 42})

        with (
            patch(
                "maxapi.dispatcher.process_update_request",
                new=AsyncMock(return_value=[fixture_message_created]),
            ),
            caplog.at_level("DEBUG", logger="dispatcher"),
        ):
            task = asyncio.create_task(dispatcher.start_polling(polling_bot))
            await asyncio.wait_for(task, STOP_TIMEOUT)
            await asyncio.wait_for(
                asyncio.gather(*dispatcher._background_tasks), STOP_TIMEOUT
            )

        assert handled == ["обработан"]
        assert _reentrancy_warnings(caplog) == []
        assert any(
            record.levelname == "DEBUG"
            and "дренировать нечего" in record.getMessage()
            for record in caplog.records
        )

    async def test_external_stop_does_not_warn(
        self, dispatcher, polling_bot, caplog
    ):
        """Штатная остановка снаружи не пишет warning о реентрантности."""
        started = asyncio.Event()
        polling_bot.get_updates = _hanging_updates(started, [])

        with caplog.at_level("WARNING", logger="dispatcher"):
            task = asyncio.create_task(dispatcher.start_polling(polling_bot))
            await asyncio.wait_for(started.wait(), STOP_TIMEOUT)
            await asyncio.wait_for(dispatcher.stop_polling(), STOP_TIMEOUT)

        assert task.done()
        assert _reentrancy_warnings(caplog) == []


# ===========================================================================
# Аварийные завершения цикла
# ===========================================================================


class TestPollingTaskFailures:
    """Внешняя отмена и фатальные ошибки цикла."""

    async def test_external_cancel_does_not_leak_tasks(
        self, dispatcher, polling_bot
    ):
        """Отмена задачи polling извне не оставляет висячих задач."""
        started = asyncio.Event()
        cancelled: list = []
        polling_bot.get_updates = _hanging_updates(started, cancelled)

        task = asyncio.create_task(dispatcher.start_polling(polling_bot))
        await asyncio.wait_for(started.wait(), STOP_TIMEOUT)

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert cancelled == [True]
        assert dispatcher.polling is False
        assert dispatcher._polling_task is None

    async def test_external_cancel_leaves_background_to_shutdown(
        self, polling_bot, fixture_message_created
    ):
        """Отмена извне не дренирует фон — это делает shutdown()."""
        dispatcher = Dispatcher(use_create_task=True)
        entered = asyncio.Event()
        release = asyncio.Event()
        handled = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            entered.set()
            await release.wait()
            handled.append(event)

        polling_bot.get_updates = _updates_once({"updates": [], "marker": 12})

        with patch(
            "maxapi.dispatcher.process_update_request",
            new=AsyncMock(return_value=[fixture_message_created]),
        ):
            task = asyncio.create_task(dispatcher.start_polling(polling_bot))
            await asyncio.wait_for(entered.wait(), STOP_TIMEOUT)

            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

            # Отмена не дождалась обработчика: он всё ещё в работе.
            assert handled == []
            assert dispatcher._background_tasks

            release.set()
            await asyncio.wait_for(dispatcher.shutdown(), STOP_TIMEOUT)

        assert handled == [fixture_message_created]
        assert dispatcher._background_tasks == set()

    async def test_invalid_token_stops_and_allows_stop_polling(
        self, dispatcher, polling_bot
    ):
        """InvalidToken пробрасывается, stop_polling после него не падает."""
        polling_bot.get_updates = AsyncMock(
            side_effect=InvalidToken("плохой токен")
        )

        with pytest.raises(InvalidToken):
            await dispatcher.start_polling(polling_bot)

        assert dispatcher.polling is False
        assert dispatcher._polling_task is None

        await asyncio.wait_for(dispatcher.stop_polling(), STOP_TIMEOUT)

    async def test_stop_polling_logs_loop_error(
        self, dispatcher, polling_bot, caplog
    ):
        """Ошибка, завершившая цикл polling, логируется при остановке."""
        entered = asyncio.Event()
        release = asyncio.Event()

        async def _failing_fetch(bot):
            entered.set()
            await release.wait()
            msg = "цикл упал"
            raise RuntimeError(msg)

        dispatcher._fetch_updates_once = _failing_fetch

        task = asyncio.create_task(dispatcher.start_polling(polling_bot))
        await asyncio.wait_for(entered.wait(), STOP_TIMEOUT)

        with caplog.at_level("ERROR", logger="dispatcher"):
            # Цикл падает уже во время ожидания его завершения.
            stop_task = asyncio.create_task(dispatcher.stop_polling())
            await asyncio.sleep(0)
            release.set()
            await asyncio.wait_for(stop_task, STOP_TIMEOUT)

        assert task.done()
        assert isinstance(task.exception(), RuntimeError)
        assert any(
            "Цикл polling завершился с ошибкой" in record.getMessage()
            for record in caplog.records
        )
