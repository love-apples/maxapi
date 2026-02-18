__all__ = [
    "Message",  # для своевременной инициализации в pydantic
    "MessageEdited",
]

from ...types.message import Message
from .update import Update


class MessageEdited(Update):
    """
    Обновление, сигнализирующее об изменении сообщения.

    Attributes:
        message (Message): Объект измененного сообщения.
    """

    message: Message

    def get_ids(self) -> tuple[int | None, int | None]:
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            Tuple[Optional[int], Optional[int]]: Идентификаторы чата и
                пользователя.
        """

        return self.message.recipient.chat_id, self.message.recipient.user_id
