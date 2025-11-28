from typing import Any, Awaitable, Callable


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
            handler (Callable): Хендлер события.
            event_object (Any): Событие.
            data (dict): Дополнительные данные.

        Returns:
            Any: Результат работы хендлера.
        """

        return await handler(event_object, data)
