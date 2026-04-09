from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..enums.chat_type import ChatType
from ..types.fetchable import ChatRef, FromUserRef
from ..types.updates.bot_added import BotAdded
from ..types.updates.bot_removed import BotRemoved
from ..types.updates.bot_started import BotStarted
from ..types.updates.bot_stopped import BotStopped
from ..types.updates.chat_title_changed import ChatTitleChanged
from ..types.updates.dialog_cleared import DialogCleared
from ..types.updates.dialog_muted import DialogMuted
from ..types.updates.dialog_removed import DialogRemoved
from ..types.updates.dialog_unmuted import DialogUnmuted
from ..types.updates.message_callback import MessageCallback
from ..types.updates.message_created import MessageCreated
from ..types.updates.message_edited import MessageEdited
from ..types.updates.message_removed import MessageRemoved
from ..types.updates.user_added import UserAdded
from ..types.updates.user_removed import UserRemoved

if TYPE_CHECKING:
    from ..bot import Bot
    from ..types.updates import UpdateUnion

_EVENTS_WITH_USER_ATTR = (
    UserAdded,
    BotAdded,
    BotRemoved,
    BotStarted,
    BotStopped,
    ChatTitleChanged,
    DialogCleared,
    DialogMuted,
    DialogUnmuted,
    DialogRemoved,
)


def _extract_chat_id(event: UpdateUnion) -> int | None:
    """Вытащить chat_id из события или вложенного message."""

    chat_id = getattr(event, "chat_id", None)

    if chat_id is None and isinstance(event, (MessageCreated, MessageEdited)):
        chat_id = event.message.recipient.chat_id

    elif chat_id is None and isinstance(event, MessageCallback):
        message = event.message
        if message is not None:
            chat_id = message.recipient.chat_id

    return chat_id


def _can_resolve_chat(event: UpdateUnion) -> bool:
    """Проверить, допустима ли загрузка chat для данного события."""

    return not isinstance(event, (DialogRemoved, BotRemoved))


async def _resolve_chat(event: UpdateUnion, bot: Bot) -> None:
    """Загружает объект чата для события."""

    if not _can_resolve_chat(event):
        return

    chat_id = _extract_chat_id(event)
    if chat_id is not None:
        event.chat = await bot.get_chat_by_id(chat_id)


def _resolve_from_user_from_payload(event: UpdateUnion) -> Any | None:
    """Определяет from_user без дополнительных API-запросов."""

    if isinstance(event, (MessageCreated, MessageEdited)):
        return getattr(event.message, "sender", None)

    if isinstance(event, MessageCallback):
        return getattr(event.callback, "user", None)

    if isinstance(event, _EVENTS_WITH_USER_ATTR):
        return event.user

    return None


async def _resolve_from_user(event: UpdateUnion, bot: Bot) -> None:
    """Определяет отправителя события."""

    payload_from_user = _resolve_from_user_from_payload(event)
    if payload_from_user is not None:
        event.from_user = payload_from_user
        return

    if isinstance(event, MessageRemoved):
        if event.chat and event.chat.type == ChatType.CHAT:
            event.from_user = await bot.get_chat_member(
                chat_id=event.chat_id, user_id=event.user_id
            )
        elif event.chat and event.chat.type == ChatType.DIALOG:
            event.from_user = event.chat

    elif isinstance(event, UserRemoved) and event.admin_id:
        event.from_user = await bot.get_chat_member(
            chat_id=event.chat_id, user_id=event.admin_id
        )


def _inject_bot(event: UpdateUnion, bot: Bot) -> None:
    """Внедряет ссылку на бота в событие, сообщение и вложения."""

    if isinstance(event, (MessageCreated, MessageEdited, MessageCallback)):
        message = event.message
        if message is not None:
            message.bot = bot
            if message.body is not None:
                for att in message.body.attachments or []:
                    if hasattr(att, "bot"):
                        att.bot = bot

    if hasattr(event, "bot"):
        event.bot = bot


async def _fetch_from_user_for_message_removed(
    event: MessageRemoved, bot: Bot
) -> Any | None:
    """Разрешить from_user для MessageRemoved по требованию."""

    chat = await event.fetch_chat()
    if chat is None:
        return None

    if chat.type == ChatType.CHAT:
        return await bot.get_chat_member(
            chat_id=event.chat_id,
            user_id=event.user_id,
        )

    if chat.type == ChatType.DIALOG:
        return chat

    return None


def _build_chat_ref(event: UpdateUnion, bot: Bot) -> ChatRef | None:
    """Построить lazy ref для chat, если его можно загрузить вручную."""

    if not _can_resolve_chat(event):
        return None

    chat_id = _extract_chat_id(event)
    if chat_id is None:
        return None

    return ChatRef(
        bot=bot,
        chat_id=chat_id,
        setter=lambda value: setattr(event, "chat", value),
    )


def _build_from_user_value(event: UpdateUnion, bot: Bot) -> Any | None:
    """Построить from_user из payload или lazy ref без сетевого запроса."""

    payload_from_user = _resolve_from_user_from_payload(event)
    if payload_from_user is not None:
        return payload_from_user

    if isinstance(event, MessageRemoved):
        return FromUserRef(
            bot=bot,
            fetcher=lambda: _fetch_from_user_for_message_removed(event, bot),
            setter=lambda value: setattr(event, "from_user", value),
            chat_id=event.chat_id,
            user_id=event.user_id,
        )

    if isinstance(event, UserRemoved) and event.admin_id:
        admin_id = event.admin_id
        return FromUserRef(
            bot=bot,
            fetcher=lambda: bot.get_chat_member(
                chat_id=event.chat_id,
                user_id=admin_id,
            ),
            setter=lambda value: setattr(event, "from_user", value),
            chat_id=event.chat_id,
            user_id=admin_id,
        )

    return None


def _attach_lazy_refs(event: UpdateUnion, bot: Bot) -> None:
    """Подготовить ручной fetch для chat/from_user без автозапросов."""

    if getattr(event, "chat", None) is None:
        chat_ref = _build_chat_ref(event, bot)
        if chat_ref is not None:
            event.chat = chat_ref

    if getattr(event, "from_user", None) is None:
        from_user = _build_from_user_value(event, bot)
        if from_user is not None:
            event.from_user = from_user


async def enrich_event(event_object: UpdateUnion, bot: Bot) -> UpdateUnion:
    """
    Дополняет объект события данными чата, пользователя и ссылкой на бота.

    Args:
        event_object (UpdateUnion): Событие, которое нужно дополнить.
        bot (Bot): Экземпляр бота.

    Returns:
        UpdateUnion: Обновлённый объект события.
    """

    _inject_bot(event_object, bot)

    if not bot.auto_requests:
        _attach_lazy_refs(event_object, bot)
        return event_object

    await _resolve_chat(event_object, bot)
    await _resolve_from_user(event_object, bot)

    return event_object
