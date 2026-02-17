import warnings

from ....enums.button_type import ButtonType
from .button import Button


class ChatButton(Button):
    """
    .. deprecated:: 0.9.14
        Используйте другие типы кнопок.

    Attributes:
        text: Текст кнопки (наследуется от Button)
        chat_title: Название чата (до 128 символов)
        chat_description: Описание чата (до 256 символов)
        start_payload: Данные, передаваемые при старте чата (до 512 символов)
        uuid: Уникальный идентификатор чата
    """

    type: ButtonType = ButtonType.CHAT
    chat_title: str
    chat_description: str | None = None
    start_payload: str | None = None
    uuid: int | None = None

    def __init__(self, **data):
        super().__init__(**data)
        warnings.warn(
            "ChatButton устарел и будет удален в будущих версиях. "
            "Используйте другие типы кнопок.",
            DeprecationWarning,
            stacklevel=2,
        )
