"""Тесты регистраций, выполненных после старта диспетчера (issue #216).

Проверяет, что хендлеры, роутеры, middleware и фильтры, добавленные
после ``startup()``, попадают в диспетчеризацию: индекс обработчиков
инвалидируется при регистрации и лениво перестраивается перед
следующим событием.
"""

import asyncio
from unittest.mock import AsyncMock

from maxapi import ErrorEvent, F
from maxapi.dispatcher import Dispatcher, Router
from maxapi.enums.update import UpdateType
from maxapi.filters.command import Command, CommandsInfo
from maxapi.filters.filter import BaseFilter
from maxapi.filters.middleware import BaseMiddleware
from maxapi.types.updates.message_created import MessageCreated

# ---------------------------------------------------------------------------
# Вспомогательные классы и функции
# ---------------------------------------------------------------------------


class TrackingMW(BaseMiddleware):
    """Middleware, отмечающая свой вызов в списке."""

    def __init__(self, name: str, log: list) -> None:
        self.name = name
        self.log = log

    async def __call__(self, handler, event_object, data):
        self.log.append(self.name)
        return await handler(event_object, data)


class BlockFilter(BaseFilter):
    """BaseFilter, не пропускающий ни одно событие."""

    async def __call__(self, event) -> bool:
        return False


class TraceFilter(BaseFilter):
    """BaseFilter, отмечающий проверку роутера и блокирующий событие."""

    def __init__(self, name: str, log: list) -> None:
        self.name = name
        self.log = log

    async def __call__(self, event) -> bool:
        self.log.append(self.name)
        return False


async def _startup(dp: Dispatcher, bot) -> None:
    """Запускает диспетчер без обращений к API."""
    dp.check_me = AsyncMock()
    await dp.startup(bot)
    assert dp._ready is True


async def _stop_polling(dp: Dispatcher) -> None:
    """Останавливает диспетчер так же, как это делает stop_polling().

    Полный цикл polling здесь не нужен: важно лишь состояние после
    остановки — ``_ready=False`` при уже построенном индексе.
    """
    dp.polling = True
    await dp.stop_polling()


class TestLateRegistration:
    """Хендлеры и роутеры, зарегистрированные после старта."""

    async def test_late_handler_on_dispatcher_is_called(
        self, dispatcher, bot, fixture_message_created
    ):
        """Хендлер, зарегистрированный после startup(), вызывается."""
        handled = []

        await _startup(dispatcher, bot)

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            handled.append(event)

        await dispatcher.handle(fixture_message_created)

        assert handled == [fixture_message_created]

    async def test_late_included_router_is_dispatched(
        self, dispatcher, bot, fixture_message_created
    ):
        """Роутер, включённый после startup(), участвует в диспетчеризации."""
        handled = []
        router = Router("late")

        @router.message_created()
        async def _handler(event: MessageCreated):
            handled.append(event)

        await _startup(dispatcher, bot)
        dispatcher.include_routers(router)

        await dispatcher.handle(fixture_message_created)

        assert handled == [fixture_message_created]

    async def test_late_handler_on_already_included_router(
        self, dispatcher, bot, fixture_message_created
    ):
        """Хендлер роутера, добавленный после старта, попадает в индекс."""
        handled = []
        router = Router("included")
        dispatcher.include_routers(router)

        await _startup(dispatcher, bot)

        @router.message_created()
        async def _handler(event: MessageCreated):
            handled.append(event)

        await dispatcher.handle(fixture_message_created)

        assert handled == [fixture_message_created]

    async def test_late_nested_router_is_dispatched(
        self, dispatcher, bot, fixture_message_created
    ):
        """Вложенный роутер, включённый в родителя после старта, работает."""
        handled = []
        parent = Router("parent")
        child = Router("child")

        @child.message_created()
        async def _handler(event: MessageCreated):
            handled.append(event)

        dispatcher.include_routers(parent)
        await _startup(dispatcher, bot)

        parent.include_routers(child)
        await dispatcher.handle(fixture_message_created)

        assert handled == [fixture_message_created]

    async def test_late_router_goes_before_dispatcher_handlers(
        self, dispatcher, bot, fixture_message_created
    ):
        """Поздно включённый роутер проверяется раньше хендлеров самого dp."""
        order: list[str] = []
        early = Router("early")
        early.filter(TraceFilter("early", order))
        late = Router("late")
        late.filter(TraceFilter("late", order))

        @dispatcher.message_created()
        async def _dp_handler(event: MessageCreated):
            order.append("dp")

        dispatcher.include_routers(early)
        await _startup(dispatcher, bot)

        dispatcher.include_routers(late)
        await dispatcher.handle(fixture_message_created)

        assert order == ["early", "late", "dp"]

    async def test_duplicate_router_after_start_warns_once(
        self, dispatcher, bot, caplog
    ):
        """О дубле, появившемся после старта, предупреждаем ровно один раз."""
        router = Router("duplicated")
        dispatcher.include_routers(router)

        await _startup(dispatcher, bot)

        with caplog.at_level("WARNING", logger="dispatcher"):
            dispatcher.include_routers(router)
            dispatcher._ensure_prepared()

            # Следующая перестройка не должна повторять предупреждение.
            dispatcher.filter(BlockFilter())
            dispatcher._ensure_prepared()

        messages = [
            record.getMessage()
            for record in caplog.records
            if "Обнаружены повторные включения роутеров" in record.getMessage()
        ]

        assert len(messages) == 1
        assert "duplicated" in messages[0]

    async def test_registrations_inside_on_started(
        self, dispatcher, bot, fixture_message_created, fixture_bot_started
    ):
        """Регистрации внутри on_started попадают в индекс сразу при старте."""
        handled = []
        router = Router("from_on_started")

        @router.message_created()
        async def _router_handler(event: MessageCreated):
            handled.append("router")

        @dispatcher.on_started()
        async def _on_started():
            dispatcher.include_routers(router)

            @dispatcher.bot_started()
            async def _dp_handler(event):
                handled.append("dispatcher")

        await _startup(dispatcher, bot)

        # Индекс перестроен до первого события
        assert dispatcher._handlers_dirty is False

        await dispatcher.handle(fixture_message_created)
        await dispatcher.handle(fixture_bot_started)

        assert handled == ["router", "dispatcher"]

    async def test_late_error_handler_is_called(
        self, dispatcher, bot, fixture_message_created
    ):
        """Обработчик ошибок, зарегистрированный после старта, срабатывает."""
        caught: list[ErrorEvent] = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            raise ValueError("boom")

        await _startup(dispatcher, bot)

        @dispatcher.errors(ValueError)
        async def _error_handler(event: ErrorEvent):
            caught.append(event)

        # Наблюдаемый эффект перестройки: сигнатура обработчика ошибки
        # разбирается только в _prepare_handlers. Пока перестройки не было,
        # func_args пуст — значит регистрация индекс действительно
        # инвалидировала, а не просто попала в список error_handlers.
        error_handler = dispatcher.error_handlers[-1]
        assert error_handler.func_args is None

        await dispatcher.handle(fixture_message_created)

        assert error_handler.func_args is not None
        assert len(caught) == 1
        assert isinstance(caught[0].exception, ValueError)


class TestLateMiddlewareAndFilters:
    """Middleware и фильтры, зарегистрированные после старта."""

    async def test_late_outer_middleware_is_applied(
        self, dispatcher, bot, fixture_message_created
    ):
        """Outer middleware, зарегистрированная после старта, вызывается."""
        log: list[str] = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            log.append("handler")

        await _startup(dispatcher, bot)
        dispatcher.register_outer_middleware(TrackingMW("outer", log))

        await dispatcher.handle(fixture_message_created)

        assert log == ["outer", "handler"]

    async def test_late_inner_middleware_is_applied(
        self, dispatcher, bot, fixture_message_created
    ):
        """Inner middleware, зарегистрированная после старта, вызывается."""
        log: list[str] = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            log.append("handler")

        await _startup(dispatcher, bot)
        dispatcher.register_inner_middleware(TrackingMW("inner", log))

        await dispatcher.handle(fixture_message_created)

        assert log == ["inner", "handler"]

    async def test_late_filter_is_applied(
        self, dispatcher, bot, fixture_message_created
    ):
        """Фильтр, добавленный после старта, блокирует событие."""
        handled = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            handled.append(event)

        await _startup(dispatcher, bot)
        dispatcher.filter(BlockFilter())

        await dispatcher.handle(fixture_message_created)

        assert handled == []

    async def test_late_magic_filter_is_applied(
        self, dispatcher, bot, fixture_message_created
    ):
        """MagicFilter из filter() попадает в filters и работает."""
        handled = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            handled.append(event)

        await _startup(dispatcher, bot)
        dispatcher.filter(F.update_type == UpdateType.BOT_STARTED)

        assert len(dispatcher.filters) == 1
        assert dispatcher.base_filters == []

        await dispatcher.handle(fixture_message_created)

        assert handled == []

    async def test_late_on_started_registration_warns(
        self, dispatcher, bot, caplog
    ):
        """on_started, зарегистрированный после подготовки, предупреждает."""
        await _startup(dispatcher, bot)

        with caplog.at_level("WARNING", logger="dispatcher"):

            @dispatcher.on_started()
            async def _on_started():
                pass

        assert any(
            "он не будет вызван" in record.getMessage()
            for record in caplog.records
        )
        assert dispatcher.on_started_func is _on_started

    async def test_late_command_handler_extracts_commands(
        self, dispatcher, bot
    ):
        """Команды поздно зарегистрированного хендлера попадают в бота."""
        await _startup(dispatcher, bot)
        assert bot.commands == []

        @dispatcher.message_created(Command("ping"))
        async def _handler(event: MessageCreated):
            """Обработчик команды.

            commands_info: Проверка связи
            """

        dispatcher._ensure_prepared()

        assert bot.commands == [
            CommandsInfo(commands=["ping"], info="Проверка связи")
        ]

    async def test_rebuild_does_not_duplicate_commands(
        self, dispatcher, bot, fixture_message_created
    ):
        """Повторные перестройки не дублируют команды бота."""

        @dispatcher.message_created(Command("ping"))
        async def _handler(event: MessageCreated):
            """Обработчик команды.

            commands_info: Проверка связи
            """

        await _startup(dispatcher, bot)

        dispatcher.filter(BlockFilter())
        await dispatcher.handle(fixture_message_created)
        dispatcher.filter(BlockFilter())
        await dispatcher.handle(fixture_message_created)

        assert bot.commands == [
            CommandsInfo(commands=["ping"], info="Проверка связи")
        ]


class TestAfterStop:
    """Регистрации после остановки диспетчера."""

    async def test_late_handler_after_stop_polling(
        self, dispatcher, bot, fixture_message_created
    ):
        """После stop_polling() новый хендлер всё равно попадает в индекс."""
        handled = []

        await _startup(dispatcher, bot)
        await _stop_polling(dispatcher)
        assert dispatcher._ready is False

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            handled.append(event)

        await dispatcher.handle(fixture_message_created)

        assert handled == [fixture_message_created]

    async def test_late_raw_handler_after_stop_polling(self, dispatcher, bot):
        """handle_raw_response видит регистрацию после stop_polling()."""
        received: list[dict] = []

        await _startup(dispatcher, bot)
        await _stop_polling(dispatcher)

        @dispatcher.raw_api_response()
        async def _handler(raw):
            received.append(raw)

        await dispatcher.handle_raw_response(
            UpdateType.RAW_API_RESPONSE, {"key": "value"}
        )

        assert received == [{"key": "value"}]

    async def test_late_outer_middleware_after_stop_polling(
        self, dispatcher, bot, fixture_message_created
    ):
        """Outer middleware, добавленная после stop_polling(), вызывается."""
        log: list[str] = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            log.append("handler")

        await _startup(dispatcher, bot)
        await _stop_polling(dispatcher)

        dispatcher.register_outer_middleware(TrackingMW("outer", log))
        await dispatcher.handle(fixture_message_created)

        assert log == ["outer", "handler"]

    async def test_startup_after_shutdown_rebuilds_index(
        self, dispatcher, bot
    ):
        """startup() после shutdown() сразу учитывает новые регистрации."""
        await _startup(dispatcher, bot)
        await dispatcher.shutdown()

        @dispatcher.message_created(Command("ping"))
        async def _handler(event: MessageCreated):
            """Обработчик команды.

            commands_info: Проверка связи
            """

        # Подготовка не повторяется (_ready остался True), но индекс и
        # bot.commands обязаны быть актуальны уже до первого события.
        await dispatcher.startup(bot)

        assert bot.handlers_commands == [
            CommandsInfo(commands=["ping"], info="Проверка связи")
        ]


class TestInvalidation:
    """Инвалидация индекса и его перестройка."""

    async def test_child_invalidation_reaches_root_after_rebuild(
        self, dispatcher, bot, fixture_message_created
    ):
        """Инвалидация от ребёнка доходит до корня и после перестройки."""
        handled: list[str] = []
        router = Router("child")
        dispatcher.include_routers(router)

        await _startup(dispatcher, bot)

        @router.bot_started()
        async def _first(event):
            handled.append("first")

        # Первая перестройка: корень становится «чистым»
        await dispatcher.handle(fixture_message_created)

        @router.message_created()
        async def _second(event: MessageCreated):
            handled.append("second")

        await dispatcher.handle(fixture_message_created)

        assert handled == ["second"]

    async def test_invalidation_reaches_all_parents(
        self, dispatcher, bot, fixture_message_created
    ):
        """Роутер в нескольких родителях инвалидирует оба дерева."""
        handled: list[str] = []
        shared = Router("shared")
        grandchild = Router("grandchild")
        other_dp = Dispatcher(router_id="other")

        @grandchild.message_created()
        async def _handler(event: MessageCreated):
            handled.append("grandchild")

        dispatcher.include_routers(shared)
        other_dp.include_routers(shared)

        await _startup(dispatcher, bot)
        await _startup(other_dp, bot)

        # Оба диспетчера уже построили свои кеши записей: включение внука
        # обязано инвалидировать оба снимка, а не только первый.
        snapshots = (
            dispatcher._cached_router_entries,
            other_dp._cached_router_entries,
        )
        assert all(snapshot is not None for snapshot in snapshots)

        shared.include_routers(grandchild)

        assert dispatcher._cached_router_entries is None
        assert other_dp._cached_router_entries is None

        await dispatcher.handle(fixture_message_created)
        await other_dp.handle(fixture_message_created)

        assert handled == ["grandchild", "grandchild"]

    async def test_unprepared_dispatcher_does_not_read_stale_index(
        self, dispatcher, bot, fixture_message_created
    ):
        """Неподготовленный диспетчер не читает чужой устаревший индекс."""
        handled: list[str] = []
        shared = Router("shared")
        other_dp = Dispatcher(router_id="unprepared")

        dispatcher.include_routers(shared)
        other_dp.include_routers(shared)

        # Индекс роутера построен первым диспетчером; второй так и не
        # стартовал и идёт по ленивому пути.
        await _startup(dispatcher, bot)

        @shared.message_created()
        async def _handler(event: MessageCreated):
            handled.append("shared")

        await other_dp.handle(fixture_message_created)

        assert handled == ["shared"]

    async def test_registration_during_dispatch_keeps_inner_middleware(
        self, dispatcher, bot, fixture_message_created
    ):
        """Регистрация во время диспетчеризации не теряет inner middleware."""
        log: list[str] = []
        late = Router("late")

        @late.message_created()
        async def _handler(event: MessageCreated):
            log.append("handler")

        class RegisteringMW(BaseMiddleware):
            """Outer middleware, включающая роутер прямо во время события."""

            async def __call__(self, handler, event_object, data):
                if late not in dispatcher.routers:
                    dispatcher.include_routers(late)
                    await asyncio.sleep(0)
                return await handler(event_object, data)

        dispatcher.register_inner_middleware(TrackingMW("inner", log))
        dispatcher.register_outer_middleware(RegisteringMW())

        await _startup(dispatcher, bot)
        await dispatcher.handle(fixture_message_created)

        # Без страховочной перестройки хендлер пошёл бы по ленивому пути
        # с mw_chain=None и глобальная inner-middleware потерялась бы.
        assert log == ["inner", "handler"]

    async def test_invalidation_with_router_cycle_does_not_hang(
        self, dispatcher, bot, fixture_message_created
    ):
        """Взаимные включения роутеров не приводят к зацикливанию."""
        handled: list[str] = []
        first = Router("first")
        second = Router("second")

        first.include_routers(second)
        second.include_routers(first)
        dispatcher.include_routers(first)

        await _startup(dispatcher, bot)

        @second.message_created()
        async def _handler(event: MessageCreated):
            handled.append("second")

        await dispatcher.handle(fixture_message_created)

        assert handled == ["second"]

    async def test_index_is_not_rebuilt_without_registrations(
        self, dispatcher, bot, fixture_message_created, monkeypatch
    ):
        """Без регистраций индекс не перестраивается на каждом событии."""
        rebuilds: list[bool] = []
        original = dispatcher._prepare_handlers

        def _counting(bot_arg, *, rebuild: bool = False) -> None:
            rebuilds.append(rebuild)
            original(bot_arg, rebuild=rebuild)

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            pass

        await _startup(dispatcher, bot)
        monkeypatch.setattr(dispatcher, "_prepare_handlers", _counting)

        await dispatcher.handle(fixture_message_created)
        await dispatcher.handle(fixture_message_created)
        assert rebuilds == []

        @dispatcher.bot_started()
        async def _late(event):
            pass

        await dispatcher.handle(fixture_message_created)
        await dispatcher.handle(fixture_message_created)
        assert rebuilds == [True]

    async def test_handle_raw_response_sees_late_handler(
        self, dispatcher, bot
    ):
        """handle_raw_response видит поздно зарегистрированный обработчик."""
        received: list[dict] = []

        await _startup(dispatcher, bot)

        @dispatcher.raw_api_response()
        async def _handler(raw):
            received.append(raw)

        await dispatcher.handle_raw_response(
            UpdateType.RAW_API_RESPONSE, {"key": "value"}
        )

        assert received == [{"key": "value"}]
