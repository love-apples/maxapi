from enum import auto, unique

from ._compat import StrEnum


@unique
class ChatType(StrEnum):
    """
    Тип чата.

    Используется для различения личных и групповых чатов.

    `DIALOG` обозначает личный диалог с пользователем.
    `CHAT` обозначает групповой чат.
    `CHANNEL` обозначает канал.
    """

    DIALOG = auto()
    CHAT = auto()
    CHANNEL = auto()
