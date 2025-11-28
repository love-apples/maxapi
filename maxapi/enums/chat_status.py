from enum import Enum


class ChatStatus(str, Enum):
    """
    Статус чата относительно пользователя или системы.

    Используется для отображения текущего состояния чата или определения доступных действий.
    """

    ACTIVE = "active"
    REMOVED = "removed"
    LEFT = "left"
    CLOSED = "closed"
    SUSPENDED = "suspended"
