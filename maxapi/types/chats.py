from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from ..enums.chat_permission import ChatPermission
from ..enums.chat_status import ChatStatus
from ..enums.chat_type import ChatType
from ..types.message import Message
from ..types.users import User


class Icon(BaseModel):
    """
    Модель иконки чата.

    Attributes:
        url (str): URL-адрес иконки.
    """

    url: str


class Chat(BaseModel):
    """
    Модель чата.

    Attributes:
        chat_id (int): Уникальный идентификатор чата.
        type (ChatType): Тип чата.
        status (ChatStatus): Статус чата.
        title (Optional[str]): Название чата.
        icon (Optional[Icon]): Иконка чата. Может быть None.
        last_event_time (int): Временная метка последнего события в чате.
        participants_count (int): Количество участников чата.
        owner_id (Optional[int]): Идентификатор владельца чата.
        participants (Optional[Dict[str, datetime]]): Словарь участников с временными метками. Может быть None.
        is_public (bool): Флаг публичности чата.
        link (Optional[str]): Ссылка на чат. Может быть None.
        description (Optional[str]): Описание чата. Может быть None.
        dialog_with_user (Optional[User]): Пользователь, с которым ведется диалог. Может быть None.
        messages_count (Optional[int]): Количество сообщений в чате. Может быть None.
        chat_message_id (Optional[str]): Идентификатор сообщения чата. Может быть None.
        pinned_message (Optional[Message]): Закрепленное сообщение. Может быть None.
    """

    chat_id: int
    type: ChatType
    status: ChatStatus
    title: Optional[str] = None
    icon: Optional[Icon] = None
    last_event_time: int
    participants_count: int
    owner_id: Optional[int] = None
    participants: Optional[Dict[str, datetime]] = None
    is_public: bool
    link: Optional[str] = None
    description: Optional[str] = None
    dialog_with_user: Optional[User] = None
    messages_count: Optional[int] = None
    chat_message_id: Optional[str] = None
    pinned_message: Optional[Message] = None

    @field_validator("participants", mode="before")
    @classmethod
    def convert_timestamps(cls, value: Dict[str, int]) -> Dict[str, datetime]:
        """
        Преобразует временные метки участников из миллисекунд в объекты datetime.

        Args:
            value (Dict[str, int]): Словарь с временными метками в миллисекундах.

        Returns:
            Dict[str, datetime]: Словарь с временными метками в формате datetime.
        """

        return {
            key: datetime.fromtimestamp(ts / 1000) for key, ts in value.items()
        }

    class Config:
        arbitrary_types_allowed = True


class Chats(BaseModel):
    """
    Модель списка чатов.

    Attributes:
        chats (List[Chat]): Список чатов. По умолчанию пустой.
        marker (Optional[int]): Маркер для пагинации. Может быть None.
    """

    chats: List[Chat] = Field(default_factory=list)
    marker: Optional[int] = None


class ChatMember(User):
    """
    Модель участника чата.

    Attributes:
        last_access_time (Optional[int]): Время последнего доступа. Может быть None.
        is_owner (Optional[bool]): Флаг владельца чата. Может быть None.
        is_admin (Optional[bool]): Флаг администратора чата. Может быть None.
        join_time (Optional[int]): Время присоединения к чату. Может быть None.
        permissions (Optional[List[ChatPermission]]): Список разрешений участника. Может быть None.
        alias (Optional[str]): Заголовок, который будет показан на клиент. Может быть None.
    """

    last_access_time: Optional[int] = None
    is_owner: Optional[bool] = None
    is_admin: Optional[bool] = None
    join_time: Optional[int] = None
    permissions: Optional[List[ChatPermission]] = None
    alias: Optional[str] = None
