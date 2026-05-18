from typing import Annotated

from pydantic import Field

from ..attachments.attachment import Attachment
from ..attachments.audio import Audio
from ..attachments.buttons.attachment_button import AttachmentButton
from ..attachments.contact import Contact
from ..attachments.file import File
from ..attachments.image import Image
from ..attachments.location import Location
from ..attachments.share import Share
from ..attachments.sticker import Sticker
from ..attachments.upload import AttachmentUpload
from ..attachments.video import Video
from ..input_media import InputMedia, InputMediaBuffer

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
