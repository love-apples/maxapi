from pydantic import BaseModel

from ...enums.upload_type import UploadType


class AttachmentPayload(BaseModel):
    """
    Полезная нагрузка вложения с токеном.

    Attributes:
        token (str): Токен для доступа или идентификации вложения.
    """

    token: str


class AttachmentUpload(BaseModel):
    """
    Вложение с полезной нагрузкой для загрузки на сервера MAX.

    Attributes:
        type (UploadType): Тип вложения (например, image, video, audio).
        payload (AttachmentPayload): Полезная нагрузка с токеном.
    """

    type: UploadType
    payload: AttachmentPayload
