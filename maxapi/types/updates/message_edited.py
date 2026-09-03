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
        message: Объект измененного сообщения.
    """

    message: Message
    update_type: Literal[UpdateType.MESSAGE_EDITED] = UpdateType.MESSAGE_EDITED

    def get_ids(self) -> tuple[int | None, int | None]:
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Как и у :class:`MessageCreated`, ``user_id`` — автор
        сообщения (``message.sender``), а не ``recipient.user_id``:
        в групповых чатах у получателя нет ``user_id``, и раньше все
        редакторы группы коллапсировали в один FSM-контекст
        ``(chat_id, None)``.

        .. versionchanged::
            Ранее возвращался ``recipient.user_id``. Это меняет
            гранулярность FSM-контекста (и ключа изоляции событий)
            для ``message_edited`` в групповых чатах: контекст стал
            per-автор, как у ``message_created``.

        Returns:
            Идентификаторы чата и пользователя.
        """

        chat_id = self.message.recipient.chat_id
        user_id = self.message.sender.user_id if self.message.sender else None
        return chat_id, user_id
