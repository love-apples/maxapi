from typing import TYPE_CHECKING, Optional

from ...types.users import User
from .update import Update

if TYPE_CHECKING:
    from ...bot import Bot


class BotRemoved(Update):
    """
    Обновление, сигнализирующее об удалении бота из чата.

    Attributes:
        chat_id (int): Идентификатор чата, из которого удалён бот.
        user (User): Объект пользователя-бота.
        is_channel (bool): Указывает, был ли пользователь добавлен в канал или нет
    """

    chat_id: int
    user: User
    is_channel: bool

    if TYPE_CHECKING:
        bot: Optional[Bot]  # pyright: ignore[reportGeneralTypeIssues]

    def get_ids(self):
        return (self.chat_id, self.user.user_id)
