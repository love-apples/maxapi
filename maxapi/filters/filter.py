from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types.updates import UpdateUnion


class BaseFilter(ABC):
    """
    Базовый класс для фильтров.

    Определяет интерфейс фильтрации событий.

    Methods:
        __call__(event): Асинхронная проверка события на соответствие фильтру.
    """
    @abstractmethod
    async def __call__(self, event: UpdateUnion) -> bool | dict:
        """Должен быть переопределен в дочернем классе."""
