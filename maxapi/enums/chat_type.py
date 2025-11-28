from enum import Enum


class ChatType(str, Enum):
    """
    Тип чата.

    Используется для различения личных и групповых чатов.
    """

    DIALOG = "dialog"
    CHAT = "chat"
    CHANNEL = "channel"
