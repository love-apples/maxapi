from ....enums.button_type import ButtonType
from .button import Button


class MessageButton(Button):
    """
    Кнопка для отправки текста

    Attributes:
        type: Тип кнопки (определяет её поведение и функционал)
        text: Отправляемый текст
    """

    type: ButtonType = ButtonType.MESSAGE
    text: str
