from typing import Annotated, Union

from pydantic import Field

from ..attachments.audio import Audio
from ..attachments.buttons.attachment_button import AttachmentButton
from ..attachments.contact import Contact
from ..attachments.file import File
from ..attachments.image import Image
from ..attachments.location import Location
from ..attachments.share import Share
from ..attachments.sticker import Sticker
from ..attachments.video import Video

Attachments = Annotated[
    Union[
        Audio,
        Video,
        File,
        Image,
        Sticker,
        Share,
        Location,
        AttachmentButton,
        Contact,
    ],
    Field(discriminator="type"),
]
