from enum import Enum


class SenderAction(str, Enum):
    """
    Действия отправителя, отображаемые получателю в интерфейсе.

    Используются для имитации активности (например, "печатает...") перед отправкой сообщения или медиа.
    """

    TYPING_ON = "typing_on"
    SENDING_PHOTO = "sending_photo"
    SENDING_VIDEO = "sending_video"
    SENDING_AUDIO = "sending_audio"
    SENDING_FILE = "sending_file"
    MARK_SEEN = "mark_seen"
