from typing import Literal

from ...enums.update import UpdateType
from .base_update import BaseUpdate


class MessageRemoved(BaseUpdate):
    """
    Класс для обработки события удаления сообщения в чате.

    Attributes:
        message_id (str): Идентификатор удаленного сообщения. Может быть None.
        chat_id (int): Идентификатор чата. Может быть None.
        user_id (int): Идентификатор пользователя. Может быть None.
    """

    message_id: str
    chat_id: int
    user_id: int
    update_type: Literal[UpdateType.MESSAGE_REMOVED] = (
        UpdateType.MESSAGE_REMOVED
    )

    def get_ids(self) -> tuple[int | None, int | None]:
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            Tuple[Optional[int], Optional[int]]: Идентификаторы чата и
                пользователя.
        """

        return self.chat_id, self.user_id
