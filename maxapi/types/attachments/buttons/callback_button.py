from typing import Optional

from ....enums.button_type import ButtonType
from ....enums.intent import Intent
from .button import Button


class CallbackButton(Button):
    """
    Кнопка с callback-действием.

    Attributes:
        type: Тип кнопки (фиксированное значение ButtonType.CALLBACK)
        text: Текст, отображаемый на кнопке (наследуется от Button)
        payload: Дополнительные данные (до 256 символов), передаваемые при нажатии
        intent: Намерение кнопки (визуальный стиль и поведение)
    """

    type: ButtonType = ButtonType.CALLBACK
    payload: Optional[str] = None
    intent: Intent = Intent.DEFAULT
