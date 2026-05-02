from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from ...enums.update import UpdateType
from ...types.bot_mixin import BotMixin
from ...types.fetchable import LazyRef
from ...types.shortcuts import ChatActionShortcutMixin, PeerShortcutMixin

if TYPE_CHECKING:
    from ...bot import Bot
    from ...types.chats import Chat, ChatMember
    from ...types.users import User


class BaseUpdate(
    BaseModel,
    BotMixin,
    PeerShortcutMixin,
    ChatActionShortcutMixin,
):
    """
    Базовая модель обновления.

    Attributes:
        update_type: Тип обновления.
        timestamp: Временная метка обновления.
    """

    update_type: UpdateType
    timestamp: int

    bot: Any | None = Field(default=None, exclude=True)  # pyright: ignore[reportRedeclaration]
    from_user: Any | None = Field(default=None, exclude=True)  # pyright: ignore[reportRedeclaration]
    chat: Any | None = Field(default=None, exclude=True)  # pyright: ignore[reportRedeclaration]

    if TYPE_CHECKING:
        bot: Bot | None  # type: ignore
        from_user: User | ChatMember | Chat | None  # type: ignore
        chat: Chat | None  # type: ignore

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    def _resolve_send_target(self) -> tuple[int | None, int | None]:
        get_ids = getattr(self, "get_ids", None)
        if not callable(get_ids):
            raise NotImplementedError(
                f"{self.__class__.__name__} не реализует get_ids()"
            )

        return get_ids()

    def _resolve_action_chat_id(self) -> int:
        chat_id, _user_id = self._resolve_send_target()
        if chat_id is None:
            raise ValueError(
                "Невозможно отправить action: chat_id отсутствует"
            )

        return chat_id

    async def _fetch_field(self, field_name: str) -> Any | None:
        """Явно получить поле события, если в нем лежит lazy ref."""

        try:
            value = getattr(self, field_name)
        except AttributeError as exc:
            msg = f"{self.__class__.__name__} has no field {field_name!r}"
            raise AttributeError(msg) from exc

        if value is None:
            return None

        if isinstance(value, LazyRef):
            return await value.fetch()

        return value

    async def fetch_chat(self) -> Chat | None:
        """Явно получить chat для события, если доступен lazy fetch."""

        return await self._fetch_field("chat")

    async def fetch_from_user(self) -> User | ChatMember | Chat | None:
        """Явно получить from_user для события, если доступен lazy fetch."""

        return await self._fetch_field("from_user")
