__all__ = [
    "Message",  # для своевременной инициализации в pydantic
    "MessageEdited",
]

from typing import Literal

from ...enums.update import UpdateType
from ...types.message import Message
from .base_update import BaseUpdate


class MessageEdited(BaseUpdate):
    """
    Обновление, сигнализирующее об изменении сообщения.

    Attributes:
        message (Message): Объект измененного сообщения.
    """

    message: Message
    update_type: Literal[UpdateType.MESSAGE_EDITED] = UpdateType.MESSAGE_EDITED

    def get_ids(self) -> tuple[int | None, int | None]:
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            Tuple[Optional[int], Optional[int]]: Идентификаторы чата и
                пользователя.
        """

        return self.message.recipient.chat_id, self.message.recipient.user_id
