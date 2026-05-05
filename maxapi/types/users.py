from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, PrivateAttr

from ..enums.chat_permission import ChatPermission
from ..types.bot_mixin import BotMixin
from ..types.command import BotCommand
from ..types.fetchable import FetchableMixin
from ..types.shortcuts import PeerShortcutMixin
from ..utils.formatting import UserMention

if TYPE_CHECKING:
    from ..bot import Bot


class User(FetchableMixin, BaseModel, BotMixin, PeerShortcutMixin):
    """
    Модель пользователя.

    Attributes:
        user_id: Уникальный идентификатор пользователя.
        first_name: Имя пользователя.
        last_name: Фамилия пользователя. Может быть None.
        username: Имя пользователя (ник). Может быть None.
        is_bot: Флаг, указывающий, является ли пользователь ботом.
        last_activity_time: Временная метка последней активности.
        description: Описание пользователя. Может быть None.
        avatar_url: URL аватара пользователя. Может быть None.
        full_avatar_url: URL полного аватара пользователя.
            Может быть None.
        commands: Список команд бота.
            Может быть None.
    """

    user_id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    is_bot: bool
    last_activity_time: int
    description: str | None = None
    avatar_url: str | None = None
    full_avatar_url: str | None = None
    commands: list[BotCommand] | None = None
    _bot: Any | None = PrivateAttr(default=None)

    @property
    def bot(self) -> Bot | None:
        return self._bot

    @bot.setter
    def bot(self, value: Bot | None) -> None:
        self._bot = value

    def _resolve_send_target(self) -> tuple[int | None, int | None]:
        return None, self.user_id

    @property
    def full_name(self) -> str:
        """Полное имя пользователя"""

        if not self.last_name:
            return self.first_name

        return f"{self.first_name} {self.last_name}"

    @property
    def mention_html(self) -> str:
        """Упоминание пользователя в формате HTML.

        Ссылка max://user/user_id, текст — полное имя из профиля MAX.
        Пример: <a href="max://user/12345">Имя Фамилия</a>
        """
        return UserMention(self.full_name, user_id=self.user_id).as_html()

    @property
    def mention_markdown(self) -> str:
        """Упоминание пользователя в формате Markdown.

        Ссылка max://user/user_id, текст — полное имя из профиля MAX.
        Пример: [Имя Фамилия](max://user/12345)
        """
        return UserMention(self.full_name, user_id=self.user_id).as_markdown()


class ChatAdmin(BaseModel):
    """
    Модель администратора чата.

    Attributes:
        user_id: Уникальный идентификатор администратора.
        permissions: Список разрешений администратора.
    """

    user_id: int
    permissions: list[ChatPermission]
    alias: str | None = None
