from typing import Literal

from ....enums.button_type import ButtonType
from .button import Button


class RequestContactButton(Button):
    """
    Кнопка с контактом

    Attributes:
        text (str): Текст кнопки
    """

    type: Literal[ButtonType.REQUEST_CONTACT] = ButtonType.REQUEST_CONTACT
    text: str
