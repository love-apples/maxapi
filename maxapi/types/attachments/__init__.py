from typing import Annotated, Any

from pydantic import Discriminator, Field, Tag

__all__ = [
    "Attachment",
    "AttachmentButton",
    "AttachmentInput",
    "AttachmentPayload",
    "AttachmentUpload",
    "Attachments",
    "Audio",
    "Button",
    "ButtonsPayload",
    "CallbackButton",
    "ChatButton",
    "ClipboardButton",
    "Contact",
    "ContactAttachmentPayload",
    "File",
    "Image",
    "InlineButtonUnion",
    "InputMedia",
    "InputMediaBuffer",
    "LinkButton",
    "Location",
    "MessageButton",
    "OpenAppButton",
    "OtherAttachmentPayload",
    "PhotoAttachmentPayload",
    "PhotoAttachmentRequestPayload",
    "PhotoToken",
    "RequestContactButton",
    "RequestGeoLocationButton",
    "Share",
    "ShareAttachmentPayload",
    "Sticker",
    "StickerAttachmentPayload",
    "UnknownAttachment",
    "Video",
    "VideoThumbnail",
    "VideoUrl",
]

from ...enums.attachment import AttachmentType
from ..input_media import InputMedia, InputMediaBuffer
from .attachment import (
    Attachment,
    ButtonsPayload,
    ContactAttachmentPayload,
    OtherAttachmentPayload,
    PhotoAttachmentPayload,
    ShareAttachmentPayload,
    StickerAttachmentPayload,
)
from .audio import Audio
from .buttons import (
    Button,
    CallbackButton,
    ChatButton,
    ClipboardButton,
    InlineButtonUnion,
    LinkButton,
    MessageButton,
    OpenAppButton,
    RequestContactButton,
    RequestGeoLocationButton,
)
from .buttons.attachment_button import AttachmentButton
from .contact import Contact
from .file import File
from .image import Image, PhotoAttachmentRequestPayload, PhotoToken
from .location import Location
from .share import Share
from .sticker import Sticker
from .unknown import UnknownAttachment
from .upload import AttachmentPayload, AttachmentUpload
from .video import Video, VideoThumbnail, VideoUrl

_KnownAttachments = Annotated[
    Audio
    | Video
    | File
    | Image
    | Sticker
    | Share
    | Location
    | AttachmentButton
    | Contact,
    Field(discriminator="type"),
]

_KNOWN_ATTACHMENT_TYPES = frozenset(AttachmentType)


def _attachment_tag(value: Any) -> str:
    """Отделить известные типы вложений от новых, ещё не описанных."""

    if isinstance(value, dict):
        attachment_type = value.get("type")
    else:
        attachment_type = getattr(value, "type", None)
    if attachment_type in _KNOWN_ATTACHMENT_TYPES:
        return "known"
    return "unknown"


Attachments = Annotated[
    Annotated[_KnownAttachments, Tag("known")]
    | Annotated[UnknownAttachment, Tag("unknown")],
    Discriminator(_attachment_tag),
]

AttachmentInput = (
    Attachment | AttachmentUpload | Attachments | InputMedia | InputMediaBuffer
)
