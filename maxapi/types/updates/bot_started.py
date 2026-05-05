from typing import TYPE_CHECKING, Literal

from ...enums.update import UpdateType
from ...types.users import User
from .base_update import BaseUpdate

if TYPE_CHECKING:
    from ...bot import Bot


class BotStarted(BaseUpdate):
    """
    Обновление, сигнализирующее о первом старте бота.

    Attributes:
        chat_id: Идентификатор чата.
        user: Пользователь (бот).
        user_locale: Локаль пользователя. Может быть None.
        payload: Дополнительные данные. Может быть None.
    """

    chat_id: int
    user: User
    user_locale: str | None = None
    payload: str | None = None
    update_type: Literal[UpdateType.BOT_STARTED] = UpdateType.BOT_STARTED

    if TYPE_CHECKING:
        bot: Bot | None  # pyright: ignore[reportGeneralTypeIssues]

    def get_ids(self):
        return self.chat_id, self.user.user_id
