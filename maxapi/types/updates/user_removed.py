from typing import Literal

from ...enums.update import UpdateType
from ...types.users import User
from .base_update import BaseUpdate


class UserRemoved(BaseUpdate):
    """
    Класс для обработки события выходе/удаления пользователя из чата.

    Attributes:
        chat_id: ID чата, где произошло событие
        user: Пользователь, удалённый из чата
        admin_id: Администратор, который удалил пользователя из чата.
            Может быть None, если пользователь покинул чат сам
        is_channel: Указывает, был ли пользователь удалён из канала или
            нет
    """

    chat_id: int
    user: User
    admin_id: int | None = None
    is_channel: bool
    update_type: Literal[UpdateType.USER_REMOVED] = UpdateType.USER_REMOVED

    def get_ids(self) -> tuple[int | None, int | None]:
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            Tuple[Optional[int], Optional[int]]: Идентификаторы чата и
                пользователя.
        """

        return self.chat_id, self.user.user_id
