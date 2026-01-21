from typing import Any


from ..context.state_machine import State
from ..storage import BaseStorage, StorageKey


class Context:
    """
    Контекст хранения данных пользователя

    Args:
        storage (BaseStorage): хранилище
        key (StorageKey): ключ в хранище
    """

    def __init__(self, storage: BaseStorage, key: StorageKey):
        self.storage = storage
        self.key = key

    async def get_data(self) -> dict[str, Any]:
        """
        Возвращает текущий контекст данных.

        Returns:
            Словарь с данными контекста
        """

        return await self.storage.get_data(key=self.key)

    async def set_data(self, data: dict[str, Any]) -> None:
        """
        Полностью заменяет контекст данных.

        Args:
            data: Новый словарь контекста
        """

        await self.storage.set_data(key=self.key, data=data)

    async def update_data(self, **kwargs: Any) -> None:
        """
        Обновляет контекст данных новыми значениями.

        Args:
            **kwargs: Пары ключ-значение для обновления
        """

        await self.storage.update_data(key=self.key, **kwargs)

    async def set_state(self, state: State | str | None = None) -> None:
        """
        Устанавливает новое состояние.

        Args:
            state: Новое состояние или None для сброса
        """

        await self.storage.set_state(key=self.key, state=state)

    async def get_state(self) -> State | str | None:
        """
        Возвращает текущее состояние.

        Returns:
            Текущее состояние или None
        """

        return await self.storage.get_state(key=self.key)

    async def clear(self) -> None:
        """
        Очищает контекст и сбрасывает состояние.
        """

        await self.storage.clear(key=self.key)
