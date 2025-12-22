from typing import Literal, Optional

from pydantic import BaseModel

from ...enums.attachment import AttachmentType
from .attachment import Attachment


class PhotoAttachmentRequestPayload(BaseModel):
    """
    Полезная нагрузка для запроса фото-вложения.

    Attributes:
        url (Optional[str]): URL изображения.
        token (Optional[str]): Токен доступа к изображению.
        photos (Optional[str]): Дополнительные данные о фотографиях.
    """

    url: Optional[str] = None
    token: Optional[str] = None
    photos: Optional[str] = None


class Image(Attachment):
    """
    Вложение с типом изображения.

    Attributes:
        type (Literal['image']): Тип вложения, всегда 'image'.
    """

    type: Literal[AttachmentType.IMAGE]  # pyright: ignore[reportIncompatibleVariableOverride]
