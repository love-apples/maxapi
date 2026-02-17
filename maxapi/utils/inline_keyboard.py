from __future__ import annotations

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
        self.payload: list[list[InlineButtonUnion]] = [[]]

    def row(self, *buttons: InlineButtonUnion) -> InlineKeyboardBuilder:
        """
        Добавить новый ряд кнопок в клавиатуру.

        Args:
            *buttons: Произвольное количество кнопок для добавления в ряд.
        """

        if not self.payload[-1]:
            self.payload[-1].extend(buttons)
        else:
            self.payload.append([*buttons])
        return self

    def add(self, *buttons: InlineButtonUnion) -> InlineKeyboardBuilder:
        """
        Добавить кнопки в последний ряд клавиатуры.

        Args:
            *buttons: Кнопки для добавления.
        """

        for button in buttons:
            self.payload[-1].append(button)
        return self

    def adjust(self, *sizes: int) -> InlineKeyboardBuilder:
        """
        Перераспределить кнопки по рядам в соответствии с указанными размерами.

        Args:
            *sizes: Количество кнопок в каждом ряду.
                   Если кнопок больше, чем сумма размеров, размеры повторяются циклично.

        Returns:
            InlineKeyboardBuilder: Текущий объект для цепочки вызовов.
        """
        if not sizes:
            sizes = (1,)

        flat_buttons = []
        for row in self.payload:
            for button in row:
                flat_buttons.append(button)

        if not flat_buttons:
            return self

        new_payload: list[list[InlineButtonUnion]] = []
        button_index = 0
        size_index = 0

        while button_index < len(flat_buttons):
            size = sizes[size_index % len(sizes)]
            if size <= 0:
                size = 1
            row_buttons = flat_buttons[button_index : button_index + size]
            new_payload.append(row_buttons)
            button_index += size
            size_index += 1

        self.payload = new_payload
        return self

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
