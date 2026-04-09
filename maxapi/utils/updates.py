from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..enums.chat_type import ChatType
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

logger = logging.getLogger(__name__)

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


async def _resolve_chat(event: UpdateUnion, bot: Bot) -> None:
    """Загружает объект чата для события."""

    if isinstance(event, (DialogRemoved, BotRemoved)):
        return

    chat_id = getattr(event, "chat_id", None)

    if chat_id is None and isinstance(event, (MessageCreated, MessageEdited)):
        chat_id = event.message.recipient.chat_id

    elif chat_id is None and isinstance(event, MessageCallback):
        message = event.message
        if message is not None:
            chat_id = message.recipient.chat_id

    if chat_id is not None:
        event.chat = await bot.get_chat_by_id(chat_id)


async def _resolve_from_user(event: UpdateUnion, bot: Bot) -> None:
    """Определяет отправителя события."""

    if isinstance(event, (MessageCreated, MessageEdited)):
        event.from_user = getattr(event.message, "sender", None)

    elif isinstance(event, MessageCallback):
        event.from_user = getattr(event.callback, "user", None)

    elif isinstance(event, MessageRemoved):
        if event.chat and event.chat.type == ChatType.CHAT:
            event.from_user = await bot.get_chat_member(
                chat_id=event.chat_id, user_id=event.user_id
            )
        elif event.chat and event.chat.type == ChatType.DIALOG:
            event.from_user = event.chat

    elif isinstance(event, UserRemoved):
        if event.admin_id:
            event.from_user = await bot.get_chat_member(
                chat_id=event.chat_id, user_id=event.admin_id
            )

    elif isinstance(event, _EVENTS_WITH_USER_ATTR):
        event.from_user = event.user


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


async def enrich_event(event_object: UpdateUnion, bot: Bot) -> UpdateUnion:
    """
    Дополняет объект события данными чата, пользователя и ссылкой на бота.

    Args:
        event_object (UpdateUnion): Событие, которое нужно дополнить.
        bot (Bot): Экземпляр бота.

    Returns:
        UpdateUnion: Обновлённый объект события.
    """

    if not bot.auto_requests:
        return event_object

    await _resolve_chat(event_object, bot)
    await _resolve_from_user(event_object, bot)
    _inject_bot(event_object, bot)

    return event_object
