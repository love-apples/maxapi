from typing import TYPE_CHECKING, Any

from ..filters.command import Command, CommandStart
from ..types.attachments.attachment import (
    Attachment,
    ButtonsPayload,
    ContactAttachmentPayload,
    OtherAttachmentPayload,
    PhotoAttachmentPayload,
    ShareAttachmentPayload,
    StickerAttachmentPayload,
)
from ..types.attachments.buttons.callback_button import CallbackButton
from ..types.attachments.buttons.chat_button import ChatButton
from ..types.attachments.buttons.clipboard_button import ClipboardButton
from ..types.attachments.buttons.link_button import LinkButton
from ..types.attachments.buttons.message_button import MessageButton
from ..types.attachments.buttons.open_app_button import OpenAppButton
from ..types.attachments.buttons.request_contact import RequestContactButton
from ..types.attachments.buttons.request_geo_location_button import (
    RequestGeoLocationButton,
)
from ..types.attachments.image import PhotoAttachmentRequestPayload
from ..types.attachments.upload import AttachmentPayload, AttachmentUpload
from ..types.callback import Callback
from ..types.chats import Chat, ChatMember, Chats, Icon
from ..types.command import BotCommand
from ..types.fetchable import ChatRef, FromUserRef, LazyRef
from ..types.message import (
    LinkedMessage,
    MarkupElement,
    MarkupLink,
    MarkupUserMention,
    Message,
    MessageBody,
    Messages,
    MessageStat,
    NewMessageLink,
    Recipient,
)
from ..types.subscription import Subscription
from ..types.updates import UpdateUnion
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
from ..types.updates.message_chat_created import MessageChatCreated
from ..types.updates.message_created import MessageCreated
from ..types.updates.message_edited import MessageEdited
from ..types.updates.message_removed import MessageRemoved
from ..types.updates.user_added import UserAdded
from ..types.updates.user_removed import UserRemoved
from ..types.users import ChatAdmin, User
from .input_media import InputMedia, InputMediaBuffer

if TYPE_CHECKING:
    from ..methods.types.sended_message import SendedMessage

__all__ = [
    "Attachment",
    "AttachmentPayload",
    "AttachmentUpload",
    "BotAdded",
    "BotCommand",
    "BotRemoved",
    "BotStarted",
    "BotStopped",
    "ButtonsPayload",
    "Callback",
    "CallbackButton",
    "Chat",
    "ChatAdmin",
    "ChatButton",
    "ChatMember",
    "ChatRef",
    "ChatTitleChanged",
    "Chats",
    "ClipboardButton",
    "Command",
    "CommandStart",
    "ContactAttachmentPayload",
    "DialogCleared",
    "DialogMuted",
    "DialogRemoved",
    "DialogUnmuted",
    "FromUserRef",
    "Icon",
    "InputMedia",
    "InputMediaBuffer",
    "LazyRef",
    "LinkButton",
    "LinkedMessage",
    "MarkupElement",
    "MarkupLink",
    "MarkupUserMention",
    "Message",
    "MessageBody",
    "MessageButton",
    "MessageCallback",
    "MessageChatCreated",
    "MessageCreated",
    "MessageEdited",
    "MessageRemoved",
    "MessageStat",
    "Messages",
    "NewMessageLink",
    "OpenAppButton",
    "OtherAttachmentPayload",
    "PhotoAttachmentPayload",
    "PhotoAttachmentRequestPayload",
    "Recipient",
    "RequestContactButton",
    "RequestGeoLocationButton",
    "SendedMessage",
    "ShareAttachmentPayload",
    "StickerAttachmentPayload",
    "Subscription",
    "UpdateUnion",
    "User",
    "UserAdded",
    "UserRemoved",
]


def __getattr__(name: str) -> Any:
    if name == "SendedMessage":
        from ..methods.types.sended_message import (  # noqa: PLC0415
            SendedMessage,
        )

        return SendedMessage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
