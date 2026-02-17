from typing import Literal

from ...enums.attachment import AttachmentType
from .attachment import Attachment


class File(Attachment):
    """
    Вложение с типом файла.

    Attributes:
        filename (Optional[str]): Имя файла.
        size (Optional[int]): Размер файла в байтах.
    """

    type: Literal[AttachmentType.FILE]
    filename: str | None = None
    size: int | None = None
