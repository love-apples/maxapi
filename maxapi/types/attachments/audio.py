from typing import Literal, Optional

from ...enums.attachment import AttachmentType

from .attachment import Attachment


class Audio(Attachment):
    
    """
    Вложение с типом аудио.

    Attributes:
        type (Literal['audio']): Тип вложения, всегда 'audio'.
        transcription (Optional[str]): Транскрипция аудио (если есть).
    """
    
    type: Literal[AttachmentType.AUDIO]
    transcription: Optional[str] = None