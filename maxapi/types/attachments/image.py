from typing import Literal

from pydantic import BaseModel

from ...enums.attachment import AttachmentType
from .attachment import Attachment


class PhotoAttachmentRequestPayload(BaseModel):
    """
    Полезная нагрузка для запроса фото-вложения.

    Attributes:
        url: URL изображения.
        token: Токен доступа к изображению.
        photos: Дополнительные данные о фотографиях.
    """

    url: str | None = None
    token: str | None = None
    photos: str | None = None


class Image(Attachment):
    """
    Вложение с типом изображения.

    Attributes:
        type: Тип вложения, всегда 'image'.
    """

    type: Literal[AttachmentType.IMAGE]  # pyright: ignore[reportIncompatibleVariableOverride]
