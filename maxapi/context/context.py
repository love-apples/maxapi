import asyncio
from typing import Any, Dict, Optional, Union

from ..context.state_machine import State


class MemoryContext:
    """
    Контекст хранения данных пользователя с блокировками.

    Args:
        chat_id (Optional[int]): Идентификатор чата
        user_id (Optional[int]): Идентификатор пользователя
    """

    def __init__(self, chat_id: Optional[int], user_id: Optional[int]):
        self.chat_id = chat_id
        self.user_id = user_id
        self._context: Dict[str, Any] = {}
        self._state: State | str | None = None
        self._lock = asyncio.Lock()

    async def get_data(self) -> dict[str, Any]:
        """
        Возвращает текущий контекст данных.

        Returns:
            Словарь с данными контекста
        """

        async with self._lock:
            return self._context

    async def set_data(self, data: dict[str, Any]):
        """
        Полностью заменяет контекст данных.

        Args:
            data: Новый словарь контекста
        """

        async with self._lock:
            self._context = data

    async def update_data(self, **kwargs: Any) -> None:
        """
        Обновляет контекст данных новыми значениями.

        Args:
            **kwargs: Пары ключ-значение для обновления
        """

        async with self._lock:
            self._context.update(kwargs)

    async def set_state(self, state: Optional[Union[State, str]] = None):
        """
        Устанавливает новое состояние.

        Args:
            state: Новое состояние или None для сброса
        """

        async with self._lock:
            self._state = state

    async def get_state(self) -> Optional[State | str]:
        """
        Возвращает текущее состояние.

        Returns:
            Текущее состояние или None
        """

        async with self._lock:
            return self._state

    async def clear(self):
        """
        Очищает контекст и сбрасывает состояние.
        """

        async with self._lock:
            self._state = None
            self._context = {}
