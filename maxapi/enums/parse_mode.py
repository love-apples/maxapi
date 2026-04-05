from enum import auto, unique

from ._compat import StrEnum


@unique
class ParseMode(StrEnum):
    """
    Формат разметки текста сообщений.

    Используется для указания способа интерпретации стилей
    (жирный, курсив, ссылки и т.д.).
    """

    MARKDOWN = auto()
    HTML = auto()


TextFormat = ParseMode
Format = TextFormat
