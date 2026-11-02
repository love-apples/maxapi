from typing import Literal

from ...enums.attachment import AttachmentType
from .attachment import Attachment, ContactAttachmentRequestPayload

__all__ = ["Contact", "ContactAttachmentRequestPayload"]


class Contact(Attachment):
    """
    Вложение с типом контакта.
    """

    type: Literal[AttachmentType.CONTACT]
