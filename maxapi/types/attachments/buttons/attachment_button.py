from typing import Literal

from ....enums.attachment import AttachmentType
from ..attachment import Attachment


class AttachmentButton(Attachment):
    """
    Модель кнопки вложения для сообщения.

    Attributes:
        type: Тип кнопки, фиксированное значение 'inline_keyboard'
        payload: Полезная нагрузка кнопки (массив рядов кнопок)
    """

    type: Literal[AttachmentType.INLINE_KEYBOARD]
