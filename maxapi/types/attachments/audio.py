from typing import Literal, Optional

from ...enums.attachment import AttachmentType
from .attachment import Attachment


class Audio(Attachment):
    """
    Вложение с типом аудио.

    Attributes:
        transcription (Optional[str]): Транскрипция аудио (если есть).
    """

    type: Literal[AttachmentType.AUDIO]  # pyright: ignore[reportIncompatibleVariableOverride]
    transcription: Optional[str] = None
