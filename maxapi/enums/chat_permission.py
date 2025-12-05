from enum import Enum


class ChatPermission(str, Enum):
    """
    Права доступа пользователя в чате.

    Используются для управления разрешениями при добавлении участников или изменении настроек чата.
    """

    READ_ALL_MESSAGES = "read_all_messages"
    ADD_REMOVE_MEMBERS = "add_remove_members"
    ADD_ADMINS = "add_admins"
    CHANGE_CHAT_INFO = "change_chat_info"
    PIN_MESSAGE = "pin_message"
    WRITE = "write"
    CAN_CALL = "can_call"
    EDIT_LINK = "edit_link"
    EDIT = "edit"
    DELETE = "delete"
    VIEW_STATS = "view_stats"
