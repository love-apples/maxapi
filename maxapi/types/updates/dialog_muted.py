from datetime import datetime
from typing import TYPE_CHECKING, Literal

from ...enums.update import UpdateType
from ...types.users import User
from ...utils.time import from_ms
from .base_update import BaseUpdate

if TYPE_CHECKING:
    from ...bot import Bot


class DialogMuted(BaseUpdate):
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
    user_locale: str | None = None
    update_type: Literal[UpdateType.DIALOG_MUTED] = UpdateType.DIALOG_MUTED

    if TYPE_CHECKING:
        bot: Bot | None  # pyright: ignore[reportGeneralTypeIssues]

    @property
    def muted_until_datetime(self) -> datetime | None:
        try:
            return from_ms(self.muted_until)
        except (OverflowError, OSError):
            return datetime.max

    def get_ids(self):
        return self.chat_id, self.user.user_id
