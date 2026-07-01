from __future__ import annotations

from typing import TYPE_CHECKING

from .filter import BaseFilter

if TYPE_CHECKING:
    from ..types.error_event import ErrorEvent


class ExceptionTypeFilter(BaseFilter):
    """
    Фильтр ошибки по типу оригинального исключения.

    Args:
        *exceptions: Типы исключений, которые нужно пропустить.
    """

    def __init__(self, *exceptions: type[BaseException]) -> None:
        self.exceptions = exceptions

    async def __call__(self, event: ErrorEvent) -> bool:
        """
        Проверяет тип ``event.exception``.
        """
        return isinstance(event.exception, self.exceptions)
