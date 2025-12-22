from typing import Literal

from ...enums.attachment import AttachmentType
from .attachment import Attachment


class Contact(Attachment):
    """
    Вложение с типом контакта.
    """

    type: Literal[AttachmentType.CONTACT]  # pyright: ignore[reportIncompatibleVariableOverride]
