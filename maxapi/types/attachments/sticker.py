from typing import Literal, Optional

from ...enums.attachment import AttachmentType
from .attachment import Attachment


class Sticker(Attachment):
    """
    Вложение с типом стикера.

    Attributes:
        width (Optional[int]): Ширина стикера в пикселях.
        height (Optional[int]): Высота стикера в пикселях.
    """

    type: Literal[AttachmentType.STICKER]  # pyright: ignore[reportIncompatibleVariableOverride]
    width: Optional[int] = None
    height: Optional[int] = None
