from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types.updates import UpdateUnion


class BaseFilter:
    """
    Базовый класс для фильтров.

    Определяет интерфейс фильтрации событий.
    Потомки должны переопределять метод __call__.

    Methods:
        __call__(event): Асинхронная проверка события на соответствие фильтру.
    """

    async def __call__(self, event: UpdateUnion) -> bool | dict:
        return True
