from datetime import datetime
from typing import TYPE_CHECKING, Optional

from ...types.users import User
from .update import Update
from ...utils.time import from_ms

if TYPE_CHECKING:
    from ...bot import Bot


class DialogMuted(Update):
    """
    Обновление, сигнализирующее об отключении оповещений от бота.

    Attributes:
        chat_id (int): Идентификатор чата.
        muted_until (int): Время до включения оповещений от бота.
        user (User): Пользователь (бот).
        user_locale (Optional[str]): Локаль пользователя.
    """

    chat_id: int
    muted_until: int
    user: User
    user_locale: Optional[str] = None

    if TYPE_CHECKING:
        bot: Optional[Bot]  # pyright: ignore[reportGeneralTypeIssues]

    @property
    def muted_until_datetime(self) -> Optional[datetime]:
        try:
            return from_ms(self.muted_until)
        except (OverflowError, OSError):
            return datetime.max

    def get_ids(self):
        return (self.chat_id, self.user.user_id)
