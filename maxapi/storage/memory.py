from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ..context import State
from .base import BaseStorage, StorageKey


@dataclass
class MemoryRecord:
    _data: dict[str, Any] = field(default_factory=dict)
    _state: State | str | None = None


class MemoryStorage(BaseStorage):
    """
    Хранилище контекстов в словаре.
    """

    def __init__(self) -> None:
        self._storage: defaultdict[StorageKey, MemoryRecord] = defaultdict(
            MemoryRecord
        )

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        return self._storage[key]._data

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        self._storage[key]._data = data

    async def update_data(self, key: StorageKey, **kwargs: Any) -> None:
        self._storage[key]._data.update(kwargs)

    async def set_state(
        self,
        key: StorageKey,
        state: State | str | None = None,
    ) -> None:
        self._storage[key]._state = state

    async def get_state(self, key: StorageKey) -> State | str | None:
        return self._storage[key]._state

    async def clear(self, key: StorageKey) -> None:
        self._storage.pop(key, None)
