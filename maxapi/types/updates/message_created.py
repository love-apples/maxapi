from __future__ import annotations

__all__ = ["Message", "MessageCreated"]

from typing import Literal

from ...enums.update import UpdateType
from ...types.message import Message
from .base_update import BaseUpdate


class MessageCreated(BaseUpdate):
    """
    Обновление, сигнализирующее о создании нового сообщения.

    Attributes:
        message (Message): Объект сообщения.
        user_locale (Optional[str]): Локаль пользователя.
    """

    message: Message
    user_locale: str | None = None
    update_type: Literal[UpdateType.MESSAGE_CREATED] = (
        UpdateType.MESSAGE_CREATED
    )

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
