from enum import Enum


class AttachmentType(str, Enum):
    """
    Типы вложений, поддерживаемые в сообщениях.

    Используется для указания типа содержимого при отправке или обработке вложений.
    """

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
    STICKER = "sticker"
    CONTACT = "contact"
    INLINE_KEYBOARD = "inline_keyboard"
    LOCATION = "location"
    SHARE = "share"
