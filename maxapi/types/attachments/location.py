from typing import Literal, Optional

from ...enums.attachment import AttachmentType
from .attachment import Attachment


class Location(Attachment):
    """
    Вложение с типом геолокации.

    Attributes:
        latitude (Optional[float]): Широта.
        longitude (Optional[float]): Долгота.
    """

    type: Literal[AttachmentType.LOCATION]  # pyright: ignore[reportIncompatibleVariableOverride]
    latitude: Optional[float] = None
    longitude: Optional[float] = None
