from enum import auto, unique

from ._compat import StrEnum


@unique
class TextStyle(StrEnum):
    """
    Стили текста, применяемые в сообщениях.

    Используются для форматирования и выделения частей текста в сообщении.
    """

    UNDERLINE = auto()
    STRONG = auto()
    EMPHASIZED = auto()
    MONOSPACED = auto()
    LINK = auto()
    STRIKETHROUGH = auto()
    USER_MENTION = auto()
    HEADING = auto()
    HIGHLIGHTED = auto()
    QUOTE = auto()
    BLOCKQUOTE = auto()
