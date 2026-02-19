from typing import TYPE_CHECKING, Literal

from ...enums.update import UpdateType
from ...types.users import User
from .base_update import BaseUpdate

if TYPE_CHECKING:
    from ...bot import Bot


class DialogRemoved(BaseUpdate):
    """
    Обновление, сигнализирующее об удалении диалога с ботом.

    Attributes:
        chat_id (int): Идентификатор чата.
        user (User): Пользователь (бот).
        user_locale (Optional[str]): Локаль пользователя.
    """

    chat_id: int
    user: User
    user_locale: str | None = None
    update_type: Literal[UpdateType.DIALOG_REMOVED] = UpdateType.DIALOG_REMOVED

    if TYPE_CHECKING:
        bot: Bot | None  # pyright: ignore[reportGeneralTypeIssues]

    def get_ids(self):
        return self.chat_id, self.user.user_id
