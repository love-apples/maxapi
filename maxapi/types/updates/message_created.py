from __future__ import annotations

from typing import Optional, Tuple

from ...types.message import Message
from .update import Update


class MessageCreated(Update):
    """
    Обновление, сигнализирующее о создании нового сообщения.

    Attributes:
        message (Message): Объект сообщения.
        user_locale (Optional[str]): Локаль пользователя.
    """

    message: Message
    user_locale: Optional[str] = None

    def get_ids(self) -> Tuple[Optional[int], int]:
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            tuple[Optional[int], int]: Идентификатор чата и пользователя.
        """

        return (self.message.recipient.chat_id, self.message.sender.user_id) # type: ignore
