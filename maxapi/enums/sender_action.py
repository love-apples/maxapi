from enum import auto, unique

from ._compat import StrEnum


@unique
class SenderAction(StrEnum):
    """
    Действия отправителя, отображаемые получателю в интерфейсе.

    Используются для имитации активности (например, "печатает...")
    перед отправкой сообщения или медиа.
    """

    TYPING_ON = auto()
    SENDING_PHOTO = auto()
    SENDING_VIDEO = auto()
    SENDING_AUDIO = auto()
    SENDING_FILE = auto()
    MARK_SEEN = auto()
