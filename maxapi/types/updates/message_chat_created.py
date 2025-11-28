from typing import Optional

from ...types.chats import Chat
from .update import Update


class MessageChatCreated(Update):
    """
    Событие создания чата.

    Attributes:
        chat (Chat): Объект чата.
        title (Optional[str]): Название чата.
        message_id (Optional[str]): ID сообщения.
        start_payload (Optional[str]): Payload для старта.
    """

    chat: Chat  # type: ignore[assignment]
    title: Optional[str] = None
    message_id: Optional[str] = None
    start_payload: Optional[str] = None

    def get_ids(self):
        return (self.chat.chat_id, self.chat.owner_id)
