from abc import ABC, abstractmethod
from typing import Any, NamedTuple

from ..context import State


class StorageKey(NamedTuple):
    chat_id: int | None
    user_id: int | None


class BaseStorage(ABC):
    """
    Базовый класс для хранилищ данных чатов
    """

    @abstractmethod
    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        """
        Возвращает текущие данные.

        Args:
            key: Ключ в хранилище

        Returns:
            Словарь с данными
        """

    @abstractmethod
    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        """
        Полностью заменяет данные.

        Args:
            key: Ключ в хранилище
            data: Новый словарь
        """

    @abstractmethod
    async def update_data(self, key: StorageKey, **kwargs: Any) -> None:
        """
        Обновляет данные новыми значениями.

        Args:
            key: Ключ в хранилище
            **kwargs: Пары ключ-значение для обновления
        """

    @abstractmethod
    async def set_state(
        self,
        key: StorageKey,
        state: State | str | None = None,
    ) -> None:
        """
        Устанавливает новое состояние.

        Args:
            key: Ключ в хранилище
            state: Новое состояние или None для сброса
        """

    @abstractmethod
    async def get_state(self, key: StorageKey) -> State | str | None:
        """
        Возвращает текущее состояние.

        Args:
            key: Ключ в хранилище

        Returns:
            Текущее состояние или None
        """

    @abstractmethod
    async def clear(self, key: StorageKey) -> None:
        """
        Очищает данные и сбрасывает состояние.

        Args:
            key: Ключ в хранилище
        """
