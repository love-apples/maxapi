from typing import Literal
from ...enums.attachment import AttachmentType

from .attachment import Attachment


class Contact(Attachment):
    
    """
    Вложение с типом контакта.

    Attributes:
        type (Literal['contact']): Тип вложения, всегда 'contact'.
    """
    
    type: Literal[AttachmentType.CONTACT]