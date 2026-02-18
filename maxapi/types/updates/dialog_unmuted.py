from typing import TYPE_CHECKING

from ...types.users import User
from .update import Update

if TYPE_CHECKING:
    from ...bot import Bot


class DialogUnmuted(Update):
    """
    Обновление, сигнализирующее о включении оповещений от бота.

    Attributes:
        chat_id (int): Идентификатор чата.
        user (User): Пользователь (бот).
        user_locale (Optional[str]): Локаль пользователя.
    """

    chat_id: int
    user: User
    user_locale: str | None = None

    if TYPE_CHECKING:
        bot: Bot | None

    def get_ids(self):
        return self.chat_id, self.user.user_id
