from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)

from ..enums.chat_permission import ChatPermission
from ..enums.chat_status import ChatStatus
from ..enums.chat_type import ChatType
from ..types.message import Message
from ..types.users import User
from ..utils.time import from_ms, to_ms


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
    title: str | None = None
    icon: Icon | None = None
    last_event_time: int
    participants_count: int
    owner_id: int | None = None
    participants: dict[str, datetime] | None = None
    is_public: bool
    link: str | None = None
    description: str | None = None
    dialog_with_user: User | None = None
    messages_count: int | None = None
    chat_message_id: str | None = None
    pinned_message: Message | None = None

    @field_validator("participants", mode="before")
    @classmethod
    def convert_timestamps(
        cls,
        value: dict[str, int] | None,
    ) -> dict[str, datetime | None] | None:
        """
        Преобразовать временные метки участников из миллисекунд
        в объекты datetime.

        Args:
            value (Optional[Dict[str, int]]): Словарь с временными
                метками в миллисекундах. Может быть None, если участников нет.

        Returns:
            Optional[Dict[str, Optional[datetime]]]: Словарь с
                временными метками в формате datetime. Может быть None,
                если входное значение было None.
        """
        if value is None:
            return None

        return {key: from_ms(ts) for key, ts in value.items()}

    @field_serializer("participants")
    def serialize_participants(self, value: dict[str, datetime] | None, info):
        """Serialize participants dict: datetime -> milliseconds"""
        if value is None:
            return None
        return {key: to_ms(dt) for key, dt in value.items()}

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


class Chats(BaseModel):
    """
    Модель списка чатов.

    Attributes:
        chats (List[Chat]): Список чатов. По умолчанию пустой.
        marker (Optional[int]): Маркер для пагинации. Может быть None.
    """

    chats: list[Chat] = Field(default_factory=list)
    marker: int | None = None


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

    last_access_time: int | None = None
    is_owner: bool | None = None
    is_admin: bool | None = None
    join_time: int | None = None
    permissions: list[ChatPermission] | None = None
    alias: str | None = None
