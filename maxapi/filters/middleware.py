from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeAlias

if TYPE_CHECKING:
    from ..types.updates import UpdateUnion

#: Звено middleware-цепочки или финальный обработчик события.
HandlerCallable: TypeAlias = Callable[
    ["UpdateUnion", dict[str, Any]],
    Awaitable[Any],
]


class BaseMiddleware:
    """
    Базовый класс для мидлварей.

    Используется для обработки события до и после вызова хендлера.
    """

    async def __call__(
        self,
        handler: HandlerCallable,
        event_object: UpdateUnion,
        data: dict[str, Any],
    ) -> Any:
        """
        Вызывает хендлер с переданным событием и данными.

        Args:
            handler (HandlerCallable): Хендлер события.
            event_object (UpdateUnion): Событие.
            data (dict): Дополнительные данные.

        Returns:
            Any: Результат работы хендлера.
        """

        return await handler(event_object, data)
