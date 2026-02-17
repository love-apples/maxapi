from __future__ import annotations

from typing import TYPE_CHECKING

from .update import Update

if TYPE_CHECKING:
    from ...types.message import Message


class MessageCreated(Update):
    """
    Обновление, сигнализирующее о создании нового сообщения.

    Attributes:
        message (Message): Объект сообщения.
        user_locale (Optional[str]): Локаль пользователя.
    """

    message: Message
    user_locale: str | None = None

    def get_ids(self) -> tuple[int | None, int | None]:
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            tuple[Optional[int], Optional[int]]: Идентификатор чата и
                пользователя.
        """

        chat_id = self.message.recipient.chat_id
        user_id = self.message.sender.user_id if self.message.sender else None
        return chat_id, user_id
