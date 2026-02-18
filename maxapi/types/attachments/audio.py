from typing import Literal

from ...enums.attachment import AttachmentType
from .attachment import Attachment


class Audio(Attachment):
    """
    Вложение с типом аудио.

    Attributes:
        transcription (Optional[str]): Транскрипция аудио (если есть).
    """

    type: Literal[AttachmentType.AUDIO]
    transcription: str | None = None
