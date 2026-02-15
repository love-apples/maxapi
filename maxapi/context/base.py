from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union

from ..context.state_machine import State


class BaseContext(ABC):
    """
    Абстрактный базовый класс для контекста хранения данных пользователя.
    """

    def __init__(
        self, chat_id: Optional[int], user_id: Optional[int], **kwargs: Any
    ) -> None:
        self.chat_id = chat_id
        self.user_id = user_id

    @abstractmethod
    async def get_data(self) -> Dict[str, Any]:
        """Возвращает текущий контекст данных."""
        pass

    @abstractmethod
    async def set_data(self, data: Dict[str, Any]) -> None:
        """Полностью заменяет контекст данных."""
        pass

    @abstractmethod
    async def update_data(self, **kwargs: Any) -> None:
        """Обновляет контекст данных новыми значениями."""
        pass

    @abstractmethod
    async def set_state(
        self, state: Optional[Union[State, str]] = None
    ) -> None:
        """Устанавливает новое состояние."""
        pass

    @abstractmethod
    async def get_state(self) -> Optional[Union[State, str]]:
        """Возвращает текущее состояние."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Очищает контекст и сбрасывает состояние."""
        pass
