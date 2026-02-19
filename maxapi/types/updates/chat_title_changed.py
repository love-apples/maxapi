from typing import TYPE_CHECKING, Literal

from ...enums.update import UpdateType
from ...types.users import User
from .base_update import BaseUpdate

if TYPE_CHECKING:
    from ...bot import Bot


class ChatTitleChanged(BaseUpdate):
    """
    Обновление, сигнализирующее об изменении названия чата.

    Attributes:
        chat_id (Optional[int]): Идентификатор чата.
        user (User): Пользователь, совершивший изменение.
        title (str): Новое название чата.
    """

    chat_id: int
    user: User
    title: str
    update_type: Literal[UpdateType.CHAT_TITLE_CHANGED] = (
        UpdateType.CHAT_TITLE_CHANGED
    )

    if TYPE_CHECKING:
        bot: Bot | None  # pyright: ignore[reportGeneralTypeIssues]

    def get_ids(self):
        return self.chat_id, self.user.user_id
