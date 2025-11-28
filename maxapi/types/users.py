from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from ..enums.chat_permission import ChatPermission
from ..types.command import BotCommand


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
        full_avatar_url (Optional[str]): URL полного аватара пользователя. Может быть None.
        commands (Optional[List[BotCommand]]): Список команд бота. Может быть None.
    """

    user_id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    is_bot: bool
    last_activity_time: int
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    full_avatar_url: Optional[str] = None
    commands: Optional[List[BotCommand]] = None

    @property
    def full_name(self):
        if self.last_name is None:
            return self.first_name

        return f"{self.first_name} {self.last_name}"

    class Config:
        json_encoders = {datetime: lambda v: int(v.timestamp() * 1000)}


class ChatAdmin(BaseModel):
    """
    Модель администратора чата.

    Attributes:
        user_id (int): Уникальный идентификатор администратора.
        permissions (List[ChatPermission]): Список разрешений администратора.
    """

    user_id: int
    permissions: List[ChatPermission]
