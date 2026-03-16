from pydantic import BaseModel

from ..enums.chat_permission import ChatPermission
from ..types.command import BotCommand
from ..utils.formatting import UserMention


class User(BaseModel):
    """
    Модель пользователя.

    Attributes:
        user_id (int): Уникальный идентификатор пользователя.
        first_name (str): Имя пользователя.
        last_name (Optional[str]): Фамилия пользователя. Может быть None.
        username (Optional[str]): Имя пользователя (ник). Может быть None.
        is_bot (bool): Флаг, указывающий, является ли пользователь ботом.
        last_activity_time (int): Временная метка последней активности.
        description (Optional[str]): Описание пользователя. Может быть None.
        avatar_url (Optional[str]): URL аватара пользователя. Может быть None.
        full_avatar_url (Optional[str]): URL полного аватара пользователя.
            Может быть None.
        commands (Optional[List[BotCommand]]): Список команд бота.
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

    @property
    def full_name(self) -> str:
        """Полное имя пользователя"""

        if self.last_name is None:
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
        user_id (int): Уникальный идентификатор администратора.
        permissions (List[ChatPermission]): Список разрешений администратора.
    """

    user_id: int
    permissions: list[ChatPermission]
