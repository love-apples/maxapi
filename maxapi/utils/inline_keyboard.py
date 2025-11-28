from typing import List

from ..enums.attachment import AttachmentType
from ..types.attachments.attachment import Attachment, ButtonsPayload
from ..types.attachments.buttons import InlineButtonUnion


class InlineKeyboardBuilder:
    """
    Конструктор инлайн-клавиатур.

    Позволяет удобно собирать кнопки в ряды и формировать из них клавиатуру
    для отправки в сообщениях.
    """

    def __init__(self):
        self.payload: List[List[InlineButtonUnion]] = [[]]

    def row(self, *buttons: InlineButtonUnion):
        """
        Добавить новый ряд кнопок в клавиатуру.

        Args:
            *buttons: Произвольное количество кнопок для добавления в ряд.
        """

        self.payload.append([*buttons])

    def add(self, button: InlineButtonUnion):
        """
        Добавить кнопку в последний ряд клавиатуры.

        Args:
            button: Кнопка для добавления.
        """

        self.payload[-1].append(button)

    def as_markup(self) -> Attachment:
        """
        Собрать клавиатуру в объект для отправки.

        Returns:
            Attachment: Объект вложения с типом INLINE_KEYBOARD.
        """

        return Attachment(
            type=AttachmentType.INLINE_KEYBOARD,
            payload=ButtonsPayload(buttons=self.payload),
        )  # type: ignore
