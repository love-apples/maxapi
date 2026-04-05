from enum import auto, unique

from ._compat import StrEnum


@unique
class AttachmentType(StrEnum):
    """
    Типы вложений, поддерживаемые в сообщениях.

    Используется для указания типа содержимого при отправке или
    обработке вложений.
    """

    IMAGE = auto()
    VIDEO = auto()
    AUDIO = auto()
    FILE = auto()
    STICKER = auto()
    CONTACT = auto()
    INLINE_KEYBOARD = auto()
    LOCATION = auto()
    SHARE = auto()
