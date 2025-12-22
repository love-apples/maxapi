from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field

from ...enums.update import UpdateType
from ...types.bot_mixin import BotMixin

if TYPE_CHECKING:
    from ...bot import Bot
    from ...types.chats import Chat
    from ...types.users import User


class Update(BaseModel, BotMixin):
    """
    Базовая модель обновления.

    Attributes:
        update_type (UpdateType): Тип обновления.
        timestamp (int): Временная метка обновления.
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
