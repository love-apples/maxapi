from enum import Enum


class UpdateType(str, Enum):
    """
    Типы обновлений (ивентов) от API.

    Используются для обработки различных событий в боте или чате.
    """

    MESSAGE_CREATED = "message_created"
    BOT_ADDED = "bot_added"
    BOT_REMOVED = "bot_removed"
    BOT_STARTED = "bot_started"
    CHAT_TITLE_CHANGED = "chat_title_changed"
    MESSAGE_CALLBACK = "message_callback"
    MESSAGE_CHAT_CREATED = "message_chat_created"
    MESSAGE_EDITED = "message_edited"
    MESSAGE_REMOVED = "message_removed"
    USER_ADDED = "user_added"
    USER_REMOVED = "user_removed"
    BOT_STOPPED = "bot_stopped"
    DIALOG_CLEARED = "dialog_cleared"
    DIALOG_MUTED = "dialog_muted"
    DIALOG_UNMUTED = "dialog_unmuted"
    DIALOG_REMOVED = "dialog_removed"

    # Для начинки диспатчера
    ON_STARTED = "on_started"
