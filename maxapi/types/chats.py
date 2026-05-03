from __future__ import annotations

# нужен в рантайме: get_type_hints() не найдёт `builtins`,
# если импорт только под TYPE_CHECKING
import builtins  # noqa: TC003
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_serializer,
    field_validator,
)

from ..enums.chat_permission import ChatPermission  # noqa: TC001
from ..enums.chat_status import ChatStatus
from ..enums.chat_type import ChatType
from ..types.bot_mixin import BotMixin
from ..types.fetchable import FetchableMixin
from ..types.message import Message
from ..types.shortcuts import ChatActionShortcutMixin, PeerShortcutMixin
from ..utils.time import from_ms, to_ms
from .users import User

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Sequence

    from ..bot import Bot
    from ..methods.types.added_admin_chat import AddedListAdminChat
    from ..methods.types.added_members_chat import AddedMembersChat
    from ..methods.types.deleted_bot_from_chat import DeletedBotFromChat
    from ..methods.types.deleted_chat import DeletedChat
    from ..methods.types.deleted_pin_message import DeletedPinMessage
    from ..methods.types.getted_list_admin_chat import GettedListAdminChat
    from ..methods.types.getted_members_chat import GettedMembersChat
    from ..methods.types.pinned_message import PinnedMessage
    from ..methods.types.removed_admin import RemovedAdmin
    from ..methods.types.removed_member_chat import RemovedMemberChat
    from ..types.attachments.image import PhotoAttachmentRequestPayload
    from ..types.message import Messages
    from .users import ChatAdmin


class Icon(BaseModel):
    """
    Модель иконки чата.

    Attributes:
        url: URL-адрес иконки.
    """

    url: str


def _walk_member_pages(
    fetch_page: Callable[
        [int | None],
        GettedMembersChat | GettedListAdminChat,
    ],
) -> Iterator[ChatMember]:
    """Итерировать по paginated ответам и защищаться от цикла marker."""

    seen_markers: set[int] = set()
    marker: int | None = None

    while True:
        page = fetch_page(marker)

        yield from page.members

        next_marker = page.marker
        if next_marker is None:
            return

        if next_marker in seen_markers:
            raise RuntimeError(
                f"Pagination marker {next_marker} repeated during pagination"
            )

        seen_markers.add(next_marker)
        marker = next_marker


class ChatMembersManager(BotMixin):
    """High-level API для работы с участниками чата."""

    def __init__(self, *, bot: Bot | None, chat_id: int) -> None:
        self.bot = bot
        self.chat_id = chat_id

    def list(
        self,
        *,
        user_ids: list[int] | None = None,
        marker: int | None = None,
        count: int | None = None,
    ) -> GettedMembersChat:
        return self._ensure_bot().get_chat_members(
            chat_id=self.chat_id,
            user_ids=user_ids,
            marker=marker,
            count=count,
        )

    def get(self, user_id: int) -> ChatMember | None:
        return self._ensure_bot().get_chat_member(
            chat_id=self.chat_id,
            user_id=user_id,
        )

    def add(self, user_ids: Sequence[int]) -> AddedMembersChat:
        return self._ensure_bot().add_chat_members(
            chat_id=self.chat_id,
            user_ids=list(user_ids),
        )

    def kick(
        self,
        user_id: int,
        *,
        block: bool = False,
    ) -> RemovedMemberChat:
        return self._ensure_bot().kick_chat_member(
            chat_id=self.chat_id,
            user_id=user_id,
            block=block,
        )

    def me(self) -> ChatMember:
        return self._ensure_bot().get_me_from_chat(self.chat_id)

    def iter_all(
        self,
        *,
        count: int = 100,
    ) -> Iterator[ChatMember]:
        """Итерировать по всем участникам чата через пагинацию."""

        yield from _walk_member_pages(
            lambda marker: self.list(marker=marker, count=count)
        )

    def list_all(
        self,
        *,
        count: int = 100,
    ) -> builtins.list[ChatMember]:
        """Получить всех участников чата списком."""

        return list(self.iter_all(count=count))


class ChatAdminsManager(BotMixin):
    """High-level API для работы с администраторами чата."""

    def __init__(self, *, bot: Bot | None, chat_id: int) -> None:
        self.bot = bot
        self.chat_id = chat_id

    def list(
        self,
        *,
        marker: int | None = None,
    ) -> GettedListAdminChat:
        return self._ensure_bot().get_list_admin_chat(
            self.chat_id,
            marker=marker,
        )

    def add(
        self,
        admins: Sequence[ChatAdmin],
        *,
        marker: int | None = None,
    ) -> AddedListAdminChat:
        return self._ensure_bot().add_list_admin_chat(
            chat_id=self.chat_id,
            admins=list(admins),
            marker=marker,
        )

    def remove(self, user_id: int) -> RemovedAdmin:
        return self._ensure_bot().remove_admin(
            chat_id=self.chat_id,
            user_id=user_id,
        )

    def iter_all(self) -> Iterator[ChatMember]:
        """Итерировать по всем администраторам чата через пагинацию."""

        yield from _walk_member_pages(lambda marker: self.list(marker=marker))

    def list_all(self) -> builtins.list[ChatMember]:
        """Получить всех администраторов чата списком."""

        return list(self.iter_all())


class Chat(
    FetchableMixin,
    BaseModel,
    BotMixin,
    PeerShortcutMixin,
    ChatActionShortcutMixin,
):
    """
    Модель чата.

    Attributes:
        chat_id: Уникальный идентификатор чата.
        type: Тип чата.
        status: Статус чата.
        title: Название чата.
        icon: Иконка чата. Может быть None.
        last_event_time: Временная метка последнего события
            в чате.
        participants_count: Количество участников чата.
        owner_id: Идентификатор владельца чата.
        participants: Словарь участников
            с временными метками. Может быть None.
        is_public: Флаг публичности чата.
        link: Ссылка на чат. Может быть None.
        description: Описание чата. Может быть None.
        dialog_with_user: Пользователь, с которым
            ведется диалог. Может быть None.
        messages_count: Количество сообщений в чате.
            Может быть None.
        chat_message_id: Идентификатор сообщения чата.
            Может быть None.
        pinned_message: Закрепленное сообщение.
            Может быть None.
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
    _bot: Any | None = PrivateAttr(default=None)

    @property
    def bot(self) -> Bot | None:
        return self._bot

    @bot.setter
    def bot(self, value: Bot | None) -> None:
        self._bot = value

    @property
    def members(self) -> ChatMembersManager:
        """Доступ к high-level операциям над участниками чата."""

        return ChatMembersManager(bot=self.bot, chat_id=self.chat_id)

    @property
    def admins(self) -> ChatAdminsManager:
        """Доступ к high-level операциям над администраторами чата."""

        return ChatAdminsManager(bot=self.bot, chat_id=self.chat_id)

    def _resolve_send_target(self) -> tuple[int | None, int | None]:
        return self.chat_id, None

    def _resolve_action_chat_id(self) -> int:
        return self.chat_id

    @staticmethod
    def _resolve_message_id(message: Message | str) -> str:
        if isinstance(message, str):
            return message

        if message.body is None:
            raise ValueError(
                "Невозможно получить message_id: поле body отсутствует"
            )

        return message.body.mid

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
            value: Словарь с временными
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

    def edit(
        self,
        *,
        icon: PhotoAttachmentRequestPayload | None = None,
        title: str | None = None,
        pin: Message | str | None = None,
        notify: bool | None = None,
    ) -> Chat:
        """Изменить данные чата через текущий объект."""

        pin_message_id = None if pin is None else self._resolve_message_id(pin)

        return self._ensure_bot().edit_chat(
            chat_id=self.chat_id,
            icon=icon,
            title=title,
            pin=pin_message_id,
            notify=notify,
        )

    def rename(
        self,
        title: str,
        *,
        notify: bool | None = None,
    ) -> Chat:
        """Переименовать чат."""

        return self.edit(title=title, notify=notify)

    def set_title(
        self,
        title: str,
        *,
        notify: bool | None = None,
    ) -> Chat:
        """Alias для rename() с более явной семантикой."""

        return self.rename(title, notify=notify)

    def set_icon(
        self,
        icon: PhotoAttachmentRequestPayload,
        *,
        notify: bool | None = None,
    ) -> Chat:
        """Alias для edit(icon=...)."""

        return self.edit(icon=icon, notify=notify)

    def fetch_pinned_message(self) -> Message | None:
        """Получить актуально закрепленное сообщение."""

        result = self._ensure_bot().get_pin_message(self.chat_id)
        return result.message

    def pin(
        self,
        message: Message | str,
        *,
        notify: bool | None = None,
    ) -> PinnedMessage:
        """Закрепить сообщение по объекту Message или message_id."""

        return self._ensure_bot().pin_message(
            chat_id=self.chat_id,
            message_id=self._resolve_message_id(message),
            notify=notify,
        )

    def unpin(self) -> DeletedPinMessage:
        """Снять закрепленное сообщение."""

        return self._ensure_bot().delete_pin_message(self.chat_id)

    def history(
        self,
        *,
        message_ids: list[str] | None = None,
        from_time: datetime | int | None = None,
        to_time: datetime | int | None = None,
        count: int = 50,
    ) -> Messages:
        """Получить историю сообщений текущего чата."""

        return self._ensure_bot().get_messages(
            chat_id=self.chat_id,
            message_ids=message_ids,
            from_time=from_time,
            to_time=to_time,
            count=count,
        )

    def leave(self) -> DeletedBotFromChat:
        """Удалить бота из текущего чата."""

        return self._ensure_bot().delete_me_from_chat(self.chat_id)

    def delete(self) -> DeletedChat:
        """Удалить текущий чат."""

        return self._ensure_bot().delete_chat(self.chat_id)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )


class Chats(BaseModel):
    """
    Модель списка чатов.

    Attributes:
        chats: Список чатов. По умолчанию пустой.
        marker: Маркер для пагинации. Может быть None.
    """

    chats: list[Chat] = Field(default_factory=list)
    marker: int | None = None


class ChatMember(User):
    """
    Модель участника чата.

    Attributes:
        last_access_time: Время последнего доступа.
            Может быть None.
        is_owner: Флаг владельца чата. Может быть None.
        is_admin: Флаг администратора чата.
            Может быть None.
        join_time: Время присоединения к чату.
            Может быть None.
        permissions: Список разрешений
            участника. Может быть None.
        alias: Заголовок, который будет показан
            на клиент. Может быть None.
    """

    last_access_time: int | None = None
    is_owner: bool | None = None
    is_admin: bool | None = None
    join_time: int | None = None
    permissions: list[ChatPermission] | None = None
    alias: str | None = None
