from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..context.state_machine import State


class BaseContext(ABC):
    """
    Абстрактный базовый класс для контекста хранения данных пользователя.
    """

    def __init__(
        self, chat_id: int | None, user_id: int | None, **kwargs: Any
    ) -> None:
        self.chat_id = chat_id
        self.user_id = user_id

    @abstractmethod
    async def get_data(self) -> dict[str, Any]:
        """Возвращает текущий контекст данных."""

    @abstractmethod
    async def set_data(self, data: dict[str, Any]) -> None:
        """Полностью заменяет контекст данных."""

    @abstractmethod
    async def update_data(self, **kwargs: Any) -> None:
        """Обновляет контекст данных новыми значениями."""

    @abstractmethod
    async def set_state(self, state: State | str | None = None) -> None:
        """Устанавливает новое состояние."""

    @abstractmethod
    async def get_state(self) -> State | str | None:
        """Возвращает текущее состояние."""

    @abstractmethod
    async def clear(self) -> None:
        """Очищает контекст и сбрасывает состояние."""
