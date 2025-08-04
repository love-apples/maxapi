from typing import Annotated, Union

from pydantic import Field
from ..attachments.share import Share
from ..attachments.buttons.attachment_button import AttachmentButton
from ..attachments.sticker import Sticker
from ..attachments.file import File
from ..attachments.image import Image
from ..attachments.video import Video
from ..attachments.audio import Audio
from ..attachments.location import Location
from ..attachments.contact import Contact


Attachments = Annotated[Union[
    Audio,
    Video,
    File,
    Image,
    Sticker,
    Share,
    Location,
    AttachmentButton,
    Contact
], Field(discriminator='type')]