from pydantic import BaseModel

from ....enums.button_type import ButtonType


class Button(BaseModel):
    """
    Базовая модель кнопки для сообщений.

    Attributes:
        type: Тип кнопки (определяет её поведение и функционал)
        text: Текст, отображаемый на кнопке (1-64 символа)
    """

    type: ButtonType
    text: str

    class Config:
        use_enum_values = True
