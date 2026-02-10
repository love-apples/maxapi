import warnings
from typing import Optional, Tuple

from ...types.chats import Chat
from .update import Update


class MessageChatCreated(Update):
    """
    .. deprecated:: 0.9.14
        Это событие устарело и будет удалено в будущих версиях.

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

    def __init__(self, **data):
        super().__init__(**data)
        warnings.warn(
            "MessageChatCreated устарел и будет удален в будущих версиях.",
            DeprecationWarning,
            stacklevel=2,
        )

    def get_ids(self) -> Tuple[Optional[int], Optional[int]]:
        return (self.chat.chat_id, self.chat.owner_id)
