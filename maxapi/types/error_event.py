from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..context import BaseContext
    from ..exceptions.dispatcher import HandlerException, MiddlewareException
    from .updates import UpdateUnion


@dataclass(slots=True)
class ErrorEvent:
    """
    Событие ошибки в цепочке диспетчера.

    Передаётся в обработчики, зарегистрированные через
    ``Dispatcher.errors`` или ``Router.errors``.

    Attributes:
        update: Исходное событие.
        exception: Оригинальное исключение.
        handler_exception: Обёртка ошибки handler.
        middleware_exception: Обёртка ошибки middleware.
        context: FSM-контекст события.
        raw_state: Состояние FSM на момент обработки.
        router_id: Идентификатор роутера.
        process_info: Строка с диагностикой обработки.
    """

    update: UpdateUnion
    exception: BaseException
    handler_exception: HandlerException | None
    middleware_exception: MiddlewareException | None
    context: BaseContext
    raw_state: Any
    router_id: str | int | None
    process_info: str
