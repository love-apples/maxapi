from typing import TYPE_CHECKING, Literal

from ...enums.update import UpdateType
from ...types.users import User
from .base_update import BaseUpdate

if TYPE_CHECKING:
    from ...bot import Bot


class BotRemoved(BaseUpdate):
    """
    Обновление, сигнализирующее об удалении бота из чата.

    Attributes:
        chat_id (int): Идентификатор чата, из которого удалён бот.
        user (User): Объект пользователя-бота.
        is_channel (bool): Указывает, был ли пользователь добавлен
            в канал или нет
    """

    chat_id: int
    user: User
    is_channel: bool
    update_type: Literal[UpdateType.BOT_REMOVED] = UpdateType.BOT_REMOVED

    if TYPE_CHECKING:
        bot: Bot | None  # pyright: ignore[reportGeneralTypeIssues]

    def get_ids(self):
        return self.chat_id, self.user.user_id
