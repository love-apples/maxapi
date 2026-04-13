from enum import auto, unique

from ._compat import StrEnum


@unique
class ButtonType(StrEnum):
    """
    Типы кнопок, доступных в интерфейсе бота.

    Определяют поведение при нажатии на кнопку в сообщении.
    """

    REQUEST_CONTACT = auto()
    CALLBACK = auto()
    CLIPBOARD = auto()
    LINK = auto()
    REQUEST_GEO_LOCATION = auto()
    CHAT = auto()
    MESSAGE = auto()
    OPEN_APP = auto()
