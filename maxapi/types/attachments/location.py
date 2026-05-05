from typing import Literal

from ...enums.attachment import AttachmentType
from .attachment import Attachment


class Location(Attachment):
    """
    Вложение с типом геолокации.

    Attributes:
        latitude: Широта.
        longitude: Долгота.
    """

    type: Literal[AttachmentType.LOCATION]  # pyright: ignore[reportIncompatibleVariableOverride]
    latitude: float | None = None
    longitude: float | None = None
