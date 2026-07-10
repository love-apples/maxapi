from enum import auto, unique

from ._compat import StrEnum


@unique
class ChatPermission(StrEnum):
    """
    Права доступа пользователя или бота в чате или канале.

    `add_remove_members` позволяет ботам добавлять и удалять участников
    только в групповых чатах. Добавление подписчиков в канал через
    `POST /chats/{chatId}/members` не поддерживается.
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
