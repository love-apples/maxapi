from typing import Literal

from ....enums.button_type import ButtonType
from .button import Button


class ClipboardButton(Button):
    """
    Кнопка для копирования текста в буфер обмена.

    Attributes:
        type: Тип кнопки, фиксированное значение ``clipboard``.
        text: Видимый текст кнопки.
        payload: Текст, который копируется в буфер обмена при нажатии.
    """

    type: Literal[ButtonType.CLIPBOARD] = ButtonType.CLIPBOARD
    payload: str
