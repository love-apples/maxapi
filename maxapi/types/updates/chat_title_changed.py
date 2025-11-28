from typing import TYPE_CHECKING, Optional

from ...types.users import User
from .update import Update

if TYPE_CHECKING:
    from ...bot import Bot


class ChatTitleChanged(Update):
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

    if TYPE_CHECKING:
        bot: Optional[Bot]  # pyright: ignore[reportGeneralTypeIssues]

    def get_ids(self):
        return (self.chat_id, self.user.user_id)
