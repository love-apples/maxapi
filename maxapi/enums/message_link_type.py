from enum import auto, unique

from ._compat import StrEnum


@unique
class MessageLinkType(StrEnum):
    """
    Тип связи между сообщениями.

    Используется для указания типа привязки: пересылка или ответ.
    """

    FORWARD = auto()
    REPLY = auto()
