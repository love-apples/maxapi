from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from ...enums.update import UpdateType
from ...types.bot_mixin import BotMixin

if TYPE_CHECKING:
    from ...bot import Bot
    from ...types.chats import Chat
    from ...types.users import User


class BaseUpdate(BaseModel, BotMixin):
    """
    Базовая модель обновления.

    Attributes:
        update_type (UpdateType): Тип обновления.
        timestamp (int): Временная метка обновления.
    """

    update_type: UpdateType
    timestamp: int

    bot: Any | None = Field(default=None, exclude=True)  # pyright: ignore[reportRedeclaration]
    from_user: Any | None = Field(default=None, exclude=True)  # pyright: ignore[reportRedeclaration]
    chat: Any | None = Field(default=None, exclude=True)  # pyright: ignore[reportRedeclaration]

    if TYPE_CHECKING:
        bot: Bot | None  # type: ignore
        from_user: User | None  # type: ignore
        chat: Chat | None  # type: ignore

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    async def fetch_chat(self) -> Any | None:
        """Явно получить chat для события, если доступен lazy fetch."""

        chat = self.chat
        if chat is None:
            return None

        fetch = getattr(chat, "fetch", None)
        if callable(fetch):
            return await fetch()

        return chat

    async def fetch_from_user(self) -> Any | None:
        """Явно получить from_user для события, если доступен lazy fetch."""

        from_user = self.from_user
        if from_user is None:
            return None

        fetch = getattr(from_user, "fetch", None)
        if callable(fetch):
            return await fetch()

        return from_user
