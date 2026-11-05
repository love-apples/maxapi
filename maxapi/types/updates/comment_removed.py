from typing import Literal

from ...enums.update import UpdateType
from .base_update import BaseUpdate


class CommentRemoved(BaseUpdate):
    """
    Обновление, сигнализирующее об удалении комментария к посту канала.

    Бот получает это событие, только если он администратор канала
    с правом read_all_messages.

    Attributes:
        message_id: Идентификатор удалённого комментария.
        chat_id: Идентификатор канала, в котором удалён комментарий.
        user_id: Идентификатор пользователя, удалившего комментарий.
        post_id: Идентификатор поста (mid), к которому относился
            комментарий.
    """

    message_id: str
    chat_id: int
    user_id: int
    post_id: str
    update_type: Literal[UpdateType.COMMENT_REMOVED] = (
        UpdateType.COMMENT_REMOVED
    )

    def get_ids(self) -> tuple[int | None, int | None]:
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            Tuple[Optional[int], Optional[int]]: Идентификаторы канала
                и пользователя.
        """

        return self.chat_id, self.user_id
