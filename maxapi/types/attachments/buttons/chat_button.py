from typing import Optional

from ....enums.button_type import ButtonType
from .button import Button


class ChatButton(Button):
    """
    Attributes:
        text: Текст кнопки (наследуется от Button)
        chat_title: Название чата (до 128 символов)
        chat_description: Описание чата (до 256 символов)
        start_payload: Данные, передаваемые при старте чата (до 512 символов)
        uuid: Уникальный идентификатор чата
    """

    type: ButtonType = ButtonType.CHAT
    chat_title: str
    chat_description: Optional[str] = None
    start_payload: Optional[str] = None
    uuid: Optional[int] = None
