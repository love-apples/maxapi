from typing import Optional, Tuple

from .update import Update


class MessageRemoved(Update):
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

    def get_ids(self) -> Tuple[Optional[int], Optional[int]]:
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            Tuple[Optional[int], Optional[int]]: Идентификаторы чата и пользователя.
        """

        return (self.chat_id, self.user_id)
