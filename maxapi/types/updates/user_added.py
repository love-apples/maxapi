from typing import Optional, Tuple

from ...types.users import User
from .update import Update


class UserAdded(Update):
    """
    Класс для обработки события добавления пользователя в чат.

    Attributes:
        inviter_id (int): Идентификатор пользователя, добавившего нового участника. Может быть None.
        chat_id (int): Идентификатор чата. Может быть None.
        user (User): Объект пользователя, добавленного в чат.
        is_channel (bool): Указывает, был ли пользователь добавлен в канал или нет
    """

    inviter_id: Optional[int] = None
    chat_id: int
    user: User
    is_channel: bool

    def get_ids(self) -> Tuple[Optional[int], Optional[int]]:
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            Tuple[Optional[int], Optional[int]]: Идентификаторы чата и пользователя.
        """

        return (self.chat_id, self.inviter_id)
