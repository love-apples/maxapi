from typing import Literal

from ...enums.update import UpdateType
from ...types.users import User
from .base_update import BaseUpdate


class UserAdded(BaseUpdate):
    """
    Класс для обработки события добавления пользователя в чат.

    Attributes:
        inviter_id (int): Идентификатор пользователя, добавившего нового
            участника. Может быть None.
        chat_id (int): Идентификатор чата. Может быть None.
        user (User): Объект пользователя, добавленного в чат.
        is_channel (bool): Указывает, был ли пользователь добавлен
            в канал или нет
    """

    inviter_id: int | None = None
    chat_id: int
    user: User
    is_channel: bool
    update_type: Literal[UpdateType.USER_ADDED] = UpdateType.USER_ADDED

    def get_ids(self) -> tuple[int | None, int | None]:
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            Tuple[Optional[int], Optional[int]]: Идентификаторы чата и
                пользователя.
        """

        return self.chat_id, self.inviter_id
