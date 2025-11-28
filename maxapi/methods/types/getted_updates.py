from typing import TYPE_CHECKING

from ...enums.update import UpdateType
from ...types.updates.bot_added import BotAdded
from ...types.updates.bot_removed import BotRemoved
from ...types.updates.bot_started import BotStarted
from ...types.updates.bot_stopped import BotStopped
from ...types.updates.chat_title_changed import ChatTitleChanged
from ...types.updates.dialog_cleared import DialogCleared
from ...types.updates.dialog_muted import DialogMuted
from ...types.updates.dialog_removed import DialogRemoved
from ...types.updates.dialog_unmuted import DialogUnmuted
from ...types.updates.message_callback import MessageCallback
from ...types.updates.message_chat_created import MessageChatCreated
from ...types.updates.message_created import MessageCreated
from ...types.updates.message_edited import MessageEdited
from ...types.updates.message_removed import MessageRemoved
from ...types.updates.user_added import UserAdded
from ...types.updates.user_removed import UserRemoved
from ...utils.updates import enrich_event

if TYPE_CHECKING:
    from ...bot import Bot


UPDATE_MODEL_MAPPING = {
    UpdateType.BOT_ADDED: BotAdded,
    UpdateType.BOT_REMOVED: BotRemoved,
    UpdateType.BOT_STARTED: BotStarted,
    UpdateType.CHAT_TITLE_CHANGED: ChatTitleChanged,
    UpdateType.MESSAGE_CALLBACK: MessageCallback,
    UpdateType.MESSAGE_CHAT_CREATED: MessageChatCreated,
    UpdateType.MESSAGE_CREATED: MessageCreated,
    UpdateType.MESSAGE_EDITED: MessageEdited,
    UpdateType.MESSAGE_REMOVED: MessageRemoved,
    UpdateType.USER_ADDED: UserAdded,
    UpdateType.USER_REMOVED: UserRemoved,
    UpdateType.BOT_STOPPED: BotStopped,
    UpdateType.DIALOG_CLEARED: DialogCleared,
    UpdateType.DIALOG_MUTED: DialogMuted,
    UpdateType.DIALOG_UNMUTED: DialogUnmuted,
    UpdateType.DIALOG_REMOVED: DialogRemoved,
}


async def get_update_model(event: dict, bot: "Bot"):
    update_type = event["update_type"]
    model_cls = UPDATE_MODEL_MAPPING.get(update_type)

    if not model_cls:
        raise ValueError(f"Unknown update type: {update_type}")

    event_object = await enrich_event(event_object=model_cls(**event), bot=bot)

    return event_object


async def process_update_request(events: dict, bot: "Bot"):
    return [await get_update_model(event, bot) for event in events["updates"]]


async def process_update_webhook(event_json: dict, bot: "Bot"):
    return await get_update_model(bot=bot, event=event_json)
