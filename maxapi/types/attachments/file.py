from typing import Literal, Optional

from ...enums.attachment import AttachmentType

from .attachment import Attachment


class File(Attachment):
    
    """
    Вложение с типом файла.

    Attributes:
        type (Literal['file']): Тип вложения, всегда 'file'.
        filename (Optional[str]): Имя файла.
        size (Optional[int]): Размер файла в байтах.
    """
    
    type: Literal[AttachmentType.FILE]
    filename: Optional[str] = None
    size: Optional[int] = None