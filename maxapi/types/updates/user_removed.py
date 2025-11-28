from typing import Optional, Tuple

from ...types.users import User
from .update import Update


class UserRemoved(Update):
    """
    Класс для обработки события выходе/удаления пользователя из чата.

    Attributes:
        admin_id (Optional[int]): Идентификатор администратора, удалившего пользователя. None при выходе из чата самим пользователем.
        chat_id (int): Идентификатор чата. Может быть None.
        user (User): Объект пользователя, удаленного из чата.
        is_channel (bool): Указывает, был ли пользователь удален из канала или нет
    """

    admin_id: Optional[int] = None
    chat_id: int
    user: User
    is_channel: bool

    def get_ids(self) -> Tuple[Optional[int], Optional[int]]:
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            Tuple[Optional[int], Optional[int]]: Идентификаторы чата и пользователя.
        """

        return (self.chat_id, self.admin_id)
