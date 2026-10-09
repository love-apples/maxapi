from __future__ import annotations

__all__ = ["CommentEdited", "CommentMessage"]

from typing import Literal

from ...enums.update import UpdateType
from ...types.comment import CommentMessage
from .base_update import BaseUpdate


class CommentEdited(BaseUpdate):
    """
    Обновление, сигнализирующее об изменении комментария к посту канала.

    Бот получает это событие, только если он администратор канала
    с правом read_all_messages.

    Attributes:
        message: Изменённый комментарий. Поле post_message_id
            заполняется из recipient.post_id, поэтому шорткаты
            reply, edit и delete работают без доп. параметров.
        user_locale: Локаль пользователя.
    """

    message: CommentMessage
    user_locale: str | None = None
    update_type: Literal[UpdateType.COMMENT_EDITED] = UpdateType.COMMENT_EDITED

    def get_ids(self) -> tuple[int | None, int | None]:
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            tuple[Optional[int], Optional[int]]: Идентификатор канала
                и автора комментария.
        """

        chat_id = self.message.recipient.chat_id
        user_id = self.message.sender.user_id if self.message.sender else None
        return chat_id, user_id
