from __future__ import annotations

from typing import Any


class BaseFilter:
    """
    Базовый класс для фильтров.

    Определяет интерфейс фильтрации событий.
    Потомки должны переопределять метод __call__.

    Methods:
        __call__(event): Асинхронная проверка события на соответствие
            фильтру.
    """

    async def __call__(self, event: Any) -> bool | dict[str, Any]:
        return True
