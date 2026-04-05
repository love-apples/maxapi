from enum import auto, unique

from ._compat import StrEnum


@unique
class UpdateType(StrEnum):
    """
    Типы обновлений (ивентов) от API.

    Используются для обработки различных событий в боте или чате.
    """

    MESSAGE_CREATED = auto()
    BOT_ADDED = auto()
    BOT_REMOVED = auto()
    BOT_STARTED = auto()
    CHAT_TITLE_CHANGED = auto()
    MESSAGE_CALLBACK = auto()
    MESSAGE_CHAT_CREATED = auto()  # deprecated: 0.9.14
    MESSAGE_EDITED = auto()
    MESSAGE_REMOVED = auto()
    USER_ADDED = auto()
    USER_REMOVED = auto()
    BOT_STOPPED = auto()
    DIALOG_CLEARED = auto()
    DIALOG_MUTED = auto()
    DIALOG_UNMUTED = auto()
    DIALOG_REMOVED = auto()
    RAW_API_RESPONSE = auto()

    # Для начинки диспатчера
    ON_STARTED = auto()
