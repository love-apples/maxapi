"""Тесты обработчиков ошибок Dispatcher/Router."""

from maxapi import ErrorEvent, ExceptionTypeFilter, F
from maxapi.dispatcher import Dispatcher, Router
from maxapi.filters.filter import BaseFilter
from maxapi.types.updates.message_created import MessageCreated


def _setup(dp: Dispatcher, bot) -> None:
    """Стандартная инициализация dp для тестов error pipeline."""
    if dp not in dp.routers:
        dp.routers.append(dp)
    dp._prepare_handlers(bot)
    dp._global_mw_chain = dp.build_middleware_chain(
        dp.outer_middlewares, dp._process_event
    )


class ErrorDataFilter(BaseFilter):
    """Фильтр ошибки, добавляющий данные в error handler."""

    async def __call__(self, event: ErrorEvent) -> dict[str, str]:
        return {"error_text": str(event.exception)}


async def test_dispatcher_errors_handles_handler_exception(
    dispatcher, bot, fixture_message_created
):
    """Dispatcher.errors ловит ошибку handler по типу исключения."""
    caught: list[ErrorEvent] = []

    @dispatcher.message_created()
    async def _handler(event: MessageCreated):
        raise ValueError("boom")

    @dispatcher.errors(ValueError)
    async def _error_handler(event: ErrorEvent):
        caught.append(event)

    _setup(dispatcher, bot)
    await dispatcher.handle(fixture_message_created)

    assert len(caught) == 1
    assert caught[0].update is fixture_message_created
    assert isinstance(caught[0].exception, ValueError)
    assert caught[0].handler_exception is not None
    assert caught[0].middleware_exception is None


async def test_router_errors_handles_only_own_router(
    dispatcher, bot, fixture_message_created
):
    """Router.errors вызывается только для handler своего router."""
    first_router = Router("first")
    second_router = Router("second")
    caught: list[str] = []

    @first_router.message_created()
    async def _first_handler(event: MessageCreated):
        raise ValueError("first")

    @first_router.errors(ValueError)
    async def _first_error(event: ErrorEvent):
        caught.append("first")

    @second_router.errors(ValueError)
    async def _second_error(event: ErrorEvent):
        caught.append("second")

    dispatcher.include_routers(first_router, second_router)
    _setup(dispatcher, bot)
    await dispatcher.handle(fixture_message_created)

    assert caught == ["first"]


async def test_dispatcher_errors_is_fallback_for_router(
    dispatcher, bot, fixture_message_created
):
    """Dispatcher.errors срабатывает, если router.errors не подошёл."""
    router = Router("router")
    caught: list[str] = []

    @router.message_created()
    async def _handler(event: MessageCreated):
        raise ValueError("boom")

    @router.errors(TypeError)
    async def _router_error(event: ErrorEvent):
        caught.append("router")

    @dispatcher.errors(ValueError)
    async def _dispatcher_error(event: ErrorEvent):
        caught.append("dispatcher")

    dispatcher.include_routers(router)
    _setup(dispatcher, bot)
    await dispatcher.handle(fixture_message_created)

    assert caught == ["dispatcher"]


async def test_errors_supports_magic_and_base_filters(
    dispatcher, bot, fixture_message_created
):
    """Error handlers поддерживают MagicFilter и BaseFilter."""
    caught: list[str] = []

    @dispatcher.message_created()
    async def _handler(event: MessageCreated):
        raise ValueError("boom")

    @dispatcher.errors(ValueError, F.exception.args == ("boom",))
    async def _error_handler(event: ErrorEvent, error_text: str):
        caught.append(error_text)

    dispatcher.error_handlers[0].base_filters.append(ErrorDataFilter())

    _setup(dispatcher, bot)
    await dispatcher.handle(fixture_message_created)

    assert caught == ["boom"]


async def test_handled_error_suppresses_default_logging(
    dispatcher, bot, fixture_message_created, monkeypatch
):
    """Успешный errors-handler отключает стандартное логирование."""
    import maxapi.dispatcher as dp_module

    logged_calls: list[tuple] = []

    def fake_exception(msg, *args, **kwargs):
        logged_calls.append((msg, args, kwargs))

    monkeypatch.setattr(dp_module.logger_dp, "exception", fake_exception)

    @dispatcher.message_created()
    async def _handler(event: MessageCreated):
        raise ValueError("boom")

    @dispatcher.errors(ValueError)
    async def _error_handler(event: ErrorEvent):
        return None

    _setup(dispatcher, bot)
    await dispatcher.handle(fixture_message_created)

    assert logged_calls == []


async def test_unmatched_error_keeps_default_logging(
    dispatcher, bot, fixture_message_created, monkeypatch
):
    """Если errors-handler не подошёл, логирование не меняется."""
    import maxapi.dispatcher as dp_module

    logged_calls: list[tuple] = []

    def fake_exception(msg, *args, **kwargs):
        logged_calls.append((msg, args, kwargs))

    monkeypatch.setattr(dp_module.logger_dp, "exception", fake_exception)

    @dispatcher.message_created()
    async def _handler(event: MessageCreated):
        raise ValueError("boom")

    @dispatcher.errors(TypeError)
    async def _error_handler(event: ErrorEvent):
        return None

    _setup(dispatcher, bot)
    await dispatcher.handle(fixture_message_created)

    assert len(logged_calls) == 1
    assert logged_calls[0][0] == "Ошибка в обработчике: %s"


def test_public_error_exports():
    """Новые публичные типы доступны из корня пакета."""
    assert ErrorEvent.__name__ == "ErrorEvent"
    assert ExceptionTypeFilter.__name__ == "ExceptionTypeFilter"
