from enum import auto, unique

from ._compat import StrEnum


@unique
class ChatStatus(StrEnum):
    """
    Статус чата относительно пользователя или системы.

    Используется для отображения текущего состояния чата или определения
    доступных действий.
    """

    ACTIVE = auto()
    REMOVED = auto()
    LEFT = auto()
    CLOSED = auto()
    SUSPENDED = auto()
