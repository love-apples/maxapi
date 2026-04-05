from enum import auto, unique

from ._compat import StrEnum


@unique
class ChatType(StrEnum):
    """
    Тип чата.

    Используется для различения личных и групповых чатов.
    """

    DIALOG = auto()
    CHAT = auto()
    CHANNEL = auto()
