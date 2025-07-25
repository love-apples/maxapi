from __future__ import annotations
from typing import TYPE_CHECKING, Any

from ..types.updates.bot_added import BotAdded
from ..types.updates.bot_removed import BotRemoved
from ..types.updates.bot_started import BotStarted
from ..types.updates.chat_title_changed import ChatTitleChanged
from ..types.updates.message_callback import MessageCallback
from ..types.updates.message_created import MessageCreated
from ..types.updates.message_edited import MessageEdited
from ..types.updates.message_removed import MessageRemoved
from ..types.updates.user_added import UserAdded
from ..types.updates.user_removed import UserRemoved

if TYPE_CHECKING:
    from ..bot import Bot
    
    

async def enrich_event(event_object: Any, bot: Bot) -> Any:
    if not bot.auto_requests:
        return event_object

    if hasattr(event_object, 'chat_id'):
        event_object.chat = await bot.get_chat_by_id(event_object.chat_id)

    if isinstance(event_object, (MessageCreated, MessageEdited, MessageCallback)):
        event_object.chat = await bot.get_chat_by_id(event_object.message.recipient.chat_id)
        event_object.from_user = getattr(event_object.message, 'sender', None)

    elif isinstance(event_object, MessageRemoved):
        event_object.chat = await bot.get_chat_by_id(event_object.chat_id)
        event_object.from_user = await bot.get_chat_member(
            chat_id=event_object.chat_id,
            user_id=event_object.user_id
        )

    elif isinstance(event_object, UserRemoved):
        event_object.chat = await bot.get_chat_by_id(event_object.chat_id)
        if event_object.admin_id:
            event_object.from_user = await bot.get_chat_member(
                chat_id=event_object.chat_id,
                user_id=event_object.admin_id
            )

    elif isinstance(event_object, UserAdded):
        event_object.chat = await bot.get_chat_by_id(event_object.chat_id)
        event_object.from_user = event_object.user

    elif isinstance(event_object, (BotAdded, BotRemoved, BotStarted, ChatTitleChanged)):
        event_object.chat = await bot.get_chat_by_id(event_object.chat_id)
        event_object.from_user = event_object.user

    if hasattr(event_object, 'message'):
        event_object.message.bot = bot
        for att in event_object.message.body.attachments:
            if hasattr(att, 'bot'):
                att.bot = bot

    if hasattr(event_object, 'bot'):
        event_object.bot = bot

    return event_object