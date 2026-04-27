from collections.abc import Awaitable, Callable
from typing import Any


class BaseMiddleware:
    """
    Базовый класс для мидлварей.

    Используется для обработки события до и после вызова хендлера.
    """

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event_object: Any,
        data: dict[str, Any],
    ) -> Any:
        """
        Вызывает хендлер с переданным событием и данными.

        Args:
            handler: Хендлер события.
            event_object: Событие.
            data: Дополнительные данные.

        Returns:
            Any: Результат работы хендлера.
        """

        return await handler(event_object, data)
