from pydantic import BaseModel

from ...enums.upload_type import UploadType


class AttachmentPayload(BaseModel):
    """
    Полезная нагрузка вложения с токеном.

    Attributes:
        token: Токен для доступа или идентификации вложения.
    """

    token: str


class AttachmentUpload(BaseModel):
    """
    Вложение с полезной нагрузкой для загрузки на сервера MAX.

    Attributes:
        type: Тип вложения (например, image, video, audio).
        payload: Полезная нагрузка с токеном.
    """

    type: UploadType
    payload: AttachmentPayload
