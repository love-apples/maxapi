from typing import Literal

from pydantic import BaseModel

from ...enums.attachment import AttachmentType
from .attachment import Attachment


class PhotoToken(BaseModel):
    """
    Токен загруженного изображения.

    Attributes:
        token: Закодированная информация загруженного изображения.
    """

    token: str


class PhotoAttachmentRequestPayload(BaseModel):
    """
    Полезная нагрузка для запроса фото-вложения.

    Attributes:
        url: URL изображения.
        token: Токен существующего вложения.
        photos: Токены, полученные после загрузки изображений.
    """

    url: str | None = None
    token: str | None = None
    photos: dict[str, PhotoToken] | str | None = None


class Image(Attachment):
    """
    Вложение с типом изображения.

    Attributes:
        type: Тип вложения, всегда 'image'.
    """

    type: Literal[AttachmentType.IMAGE]  # pyright: ignore[reportIncompatibleVariableOverride]


__all__ = ["Image", "PhotoAttachmentRequestPayload", "PhotoToken"]
