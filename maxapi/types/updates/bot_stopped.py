from typing import TYPE_CHECKING, Literal

from ...enums.update import UpdateType
from ...types.users import User
from .base_update import BaseUpdate

if TYPE_CHECKING:
    from ...bot import Bot


class BotStopped(BaseUpdate):
    """
    Обновление, сигнализирующее об остановке бота.

    Attributes:
        chat_id (int): Идентификатор чата.
        user (User): Пользователь (бот).
        user_locale (Optional[str]): Локаль пользователя.
        payload (Optional[str]): Дополнительные данные.
    """

    chat_id: int
    user: User
    user_locale: str | None = None
    payload: str | None = None
    update_type: Literal[UpdateType.BOT_STOPPED] = UpdateType.BOT_STOPPED

    if TYPE_CHECKING:
        bot: Bot | None  # pyright: ignore[reportGeneralTypeIssues]

    def get_ids(self):
        return self.chat_id, self.user.user_id
