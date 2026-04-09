from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

from .bot_mixin import BotMixin

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from typing_extensions import Self

    from ..bot import Bot
    from .chats import Chat, ChatMember
    from .users import User

ResolvedValue = TypeVar("ResolvedValue")

_UNSET = object()


class FetchableMixin:
    """Миксин для объектов, которые уже содержат все данные."""

    async def fetch(self) -> Self:
        """Вернуть текущий объект без дополнительных запросов."""

        return self


class LazyRef(BotMixin, Generic[ResolvedValue]):
    """Ленивая ссылка на сущность, которая подгружается по запросу."""

    def __init__(
        self,
        *,
        bot: Bot,
        fetcher: Callable[[], Awaitable[ResolvedValue | None]],
        setter: Callable[[ResolvedValue | None], None],
        description: str,
    ) -> None:
        self.bot = bot
        self._fetcher = fetcher
        self._setter = setter
        self._description = description
        self._resolved: ResolvedValue | None | object = _UNSET

    async def fetch(self) -> ResolvedValue | None:
        """Загрузить значение и закешировать результат."""

        if self._resolved is _UNSET:
            value = await self._fetcher()
            self._resolved = value
            self._setter(value)

        return cast(ResolvedValue | None, self._resolved)

    def __bool__(self) -> bool:
        if self._resolved is _UNSET:
            return False
        return bool(self._resolved)

    def __getattr__(self, name: str) -> Any:
        if self._resolved is _UNSET:
            msg = (
                f"{self._description} еще не загружен. "
                "Вызовите await ref.fetch()."
            )
            raise AttributeError(msg)

        return getattr(self._resolved, name)

    def __repr__(self) -> str:
        state = "resolved" if self._resolved is not _UNSET else "pending"
        return f"{self.__class__.__name__}({self._description}, {state})"


class ChatRef(LazyRef["Chat"]):
    """Ленивая ссылка на чат события."""

    def __init__(
        self,
        *,
        bot: Bot,
        chat_id: int,
        setter: Callable[[Chat | None], None],
    ) -> None:
        self.chat_id = chat_id
        super().__init__(
            bot=bot,
            fetcher=lambda: bot.get_chat_by_id(chat_id),
            setter=setter,
            description=f"chat_id={chat_id}",
        )


class FromUserRef(LazyRef["User | ChatMember | Chat"]):
    """Ленивая ссылка на отправителя/инициатора события."""

    def __init__(
        self,
        *,
        bot: Bot,
        fetcher: Callable[[], Awaitable[User | ChatMember | Chat | None]],
        setter: Callable[[User | ChatMember | Chat | None], None],
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> None:
        self.chat_id = chat_id
        self.user_id = user_id
        description = f"chat_id={chat_id}, user_id={user_id}"
        super().__init__(
            bot=bot,
            fetcher=fetcher,
            setter=setter,
            description=description,
        )
