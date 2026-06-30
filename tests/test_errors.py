"""Тесты обработчиков ошибок Dispatcher/Router."""

from maxapi import ErrorEvent, ExceptionTypeFilter, F
from maxapi.dispatcher import Dispatcher, Router
from maxapi.filters.filter import BaseFilter
from maxapi.filters.middleware import BaseMiddleware
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


class FailingMiddleware(BaseMiddleware):
    """Middleware, падающая до вызова handler."""

    async def __call__(self, handler, event_object, data):
        raise RuntimeError("middleware boom")


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


async def test_dispatcher_error_alias_registers_handler(
    dispatcher, bot, fixture_message_created
):
    """Dispatcher.error.register регистрирует тот же error observer."""
    caught: list[str] = []

    @dispatcher.message_created()
    async def _handler(event: MessageCreated):
        raise LookupError("alias")

    async def _error_handler(event: ErrorEvent):
        caught.append(str(event.exception))

    assert dispatcher.error is dispatcher.errors
    registered = dispatcher.error.register(_error_handler, LookupError)

    _setup(dispatcher, bot)
    await dispatcher.handle(fixture_message_created)

    assert registered is _error_handler
    assert caught == ["alias"]


async def test_dispatcher_errors_handles_middleware_exception(
    dispatcher, bot, fixture_message_created
):
    """Dispatcher.errors получает MiddlewareException и оригинальную ошибку."""
    caught: list[ErrorEvent] = []

    dispatcher.register_outer_middleware(FailingMiddleware())

    @dispatcher.errors(RuntimeError)
    async def _error_handler(event: ErrorEvent):
        caught.append(event)

    _setup(dispatcher, bot)
    await dispatcher.handle(fixture_message_created)

    assert len(caught) == 1
    assert isinstance(caught[0].exception, RuntimeError)
    assert caught[0].handler_exception is None
    assert caught[0].middleware_exception is not None


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


async def test_error_handler_filters_kwargs_by_signature(
    dispatcher, bot, fixture_message_created
):
    """В error handler передаются только объявленные kwargs."""
    caught: list[str] = []

    class ExtraDataFilter(BaseFilter):
        async def __call__(self, event: ErrorEvent) -> dict[str, str]:
            return {"allowed": "yes", "ignored": "no"}

    @dispatcher.message_created()
    async def _handler(event: MessageCreated):
        raise ValueError("boom")

    @dispatcher.errors(ValueError, ExtraDataFilter())
    async def _error_handler(event: ErrorEvent, allowed: str):
        caught.append(allowed)

    _setup(dispatcher, bot)
    await dispatcher.handle(fixture_message_created)

    assert caught == ["yes"]


async def test_error_handlers_support_magic_miss_and_catch_all(
    dispatcher, bot, fixture_message_created
):
    """Error handler без аргументов ловит ошибку после miss MagicFilter."""
    caught: list[str] = []

    assert dispatcher._unwrap_dispatch_exception(ValueError("plain")).args == (
        "plain",
    )

    @dispatcher.message_created()
    async def _handler(event: MessageCreated):
        raise ValueError("actual")

    @dispatcher.errors(F.exception.args == ("other",))
    async def _missed_error_handler(event: ErrorEvent):
        caught.append("missed")

    @dispatcher.errors()
    async def _catch_all_error_handler(event: ErrorEvent):
        caught.append(str(event.exception))

    _setup(dispatcher, bot)
    await dispatcher.handle(fixture_message_created)

    assert caught == ["actual"]


async def test_error_handler_exception_is_logged_and_not_handled(
    dispatcher, bot, fixture_message_created, monkeypatch
):
    """Ошибка внутри errors-handler логируется и не глушит исходную."""
    import maxapi.dispatcher as dp_module

    logged_messages: list[str] = []

    def fake_exception(msg, *args, **kwargs):
        logged_messages.append(msg)

    monkeypatch.setattr(dp_module.logger_dp, "exception", fake_exception)

    @dispatcher.message_created()
    async def _handler(event: MessageCreated):
        raise ValueError("source")

    @dispatcher.errors(ValueError)
    async def _error_handler(event: ErrorEvent):
        raise RuntimeError("error handler")

    _setup(dispatcher, bot)
    await dispatcher.handle(fixture_message_created)

    assert logged_messages == [
        "Ошибка в обработчике ошибки: %r | исходная ошибка: %r",
        "Ошибка в обработчике: %s",
    ]


def test_error_handler_logs_unknown_filter(monkeypatch):
    """ErrorHandler сообщает о неизвестном аргументе регистрации."""
    import maxapi.filters.handler as handler_module

    logged_messages: list[str] = []

    def fake_info(msg):
        logged_messages.append(msg)

    monkeypatch.setattr(handler_module.logger_dp, "info", fake_info)

    dp = Dispatcher()

    async def _error_handler(event: ErrorEvent):
        return None

    dp.errors.register(_error_handler, object())

    assert len(dp.error_handlers) == 1
    assert dp.error_handlers[0].base_filters == []
    assert logged_messages[0].startswith("Неизвестный фильтр ошибки")


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
