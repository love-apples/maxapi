from enum import auto, unique

from ._compat import StrEnum


@unique
class ChatPermission(StrEnum):
    """
    Права доступа пользователя в чате.

    Используются для управления разрешениями при добавлении участников
    или изменении настроек чата.
    """

    READ_ALL_MESSAGES = auto()
    ADD_REMOVE_MEMBERS = auto()
    ADD_ADMINS = auto()
    CHANGE_CHAT_INFO = auto()
    PIN_MESSAGE = auto()
    WRITE = auto()
    CAN_CALL = auto()
    EDIT_LINK = auto()
    POST_EDIT_DELETE_MESSAGE = auto()
    EDIT_MESSAGE = auto()
    DELETE_MESSAGE = auto()
    EDIT = auto()
    DELETE = auto()
    VIEW_STATS = auto()
