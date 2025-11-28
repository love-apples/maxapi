from enum import Enum


class ParseMode(str, Enum):
    """
    Формат разметки текста сообщений.

    Используется для указания способа интерпретации стилей (жирный, курсив, ссылки и т.д.).
    """

    MARKDOWN = "markdown"
    HTML = "html"
