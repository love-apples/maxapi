from enum import Enum


class MessageLinkType(str, Enum):
    """
    Тип связи между сообщениями.

    Используется для указания типа привязки: пересылка или ответ.
    """

    FORWARD = "forward"
    REPLY = "reply"
