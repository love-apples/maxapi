from typing import Annotated

from pydantic import Field

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
    "Video",
    "VideoThumbnail",
    "VideoUrl",
]

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
from .upload import AttachmentPayload, AttachmentUpload
from .video import Video, VideoThumbnail, VideoUrl

Attachments = Annotated[
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

AttachmentInput = (
    Attachment | AttachmentUpload | Attachments | InputMedia | InputMediaBuffer
)
