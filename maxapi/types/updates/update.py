from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Optional, Tuple

from pydantic import BaseModel, Field

from ...enums.update import UpdateType
from ...types.bot_mixin import BotMixin

if TYPE_CHECKING:
    from ...bot import Bot
    from ...types.chats import Chat
    from ...types.users import User


class Update(BaseModel, BotMixin):
    """Базовая модель обновления.

    Attributes:
        update_type: Тип обновления.
        timestamp: Временная метка обновления.
    """

    update_type: UpdateType
    timestamp: int

    bot: Optional[Any] = Field(default=None, exclude=True)  # pyright: ignore[reportRedeclaration]
    from_user: Optional[Any] = Field(default=None, exclude=True)  # pyright: ignore[reportRedeclaration]
    chat: Optional[Any] = Field(default=None, exclude=True)  # pyright: ignore[reportRedeclaration]

    if TYPE_CHECKING:
        bot: Optional[Bot]  # type: ignore
        from_user: Optional[User]  # type: ignore
        chat: Optional[Chat]  # type: ignore

    class Config:
        arbitrary_types_allowed = True

    @abstractmethod
    def get_ids(self) -> Tuple[Optional[int], Optional[int]]:
        """Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            Tuple[Optional[int], Optional[int]]: Идентификаторы чата и пользователя.
        """
        ...
