from enum import Enum


class TextStyle(Enum):
    """
    Стили текста, применяемые в сообщениях.

    Используются для форматирования и выделения частей текста в сообщении.
    """

    UNDERLINE = "underline"
    STRONG = "strong"
    EMPHASIZED = "emphasized"
    MONOSPACED = "monospaced"
    LINK = "link"
    STRIKETHROUGH = "strikethrough"
    USER_MENTION = "user_mention"
    HEADING = "heading"
    HIGHLIGHTED = "highlighted"
