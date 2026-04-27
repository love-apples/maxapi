from typing import Literal

from ...enums.update import UpdateType
from ...types.users import User
from .base_update import BaseUpdate


class UserAdded(BaseUpdate):
    """
    Класс для обработки события добавления пользователя в чат.

    Attributes:

        chat_id: ID чата, где произошло событие
        user: Пользователь, добавленный в чат
        inviter_id: Пользователь, который добавил пользователя в чат.
            Может быть null, если пользователь присоединился к чату по
            ссылке
        is_channel: Указывает, был ли пользователь добавлен в канал или
            нет
    """

    chat_id: int
    user: User
    inviter_id: int | None = None
    is_channel: bool
    update_type: Literal[UpdateType.USER_ADDED] = UpdateType.USER_ADDED

    def get_ids(self) -> tuple[int | None, int | None]:
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            Tuple[Optional[int], Optional[int]]: Идентификаторы чата и
                пользователя.
        """

        return self.chat_id, self.user.user_id
