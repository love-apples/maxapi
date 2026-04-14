from typing import Literal

from ...enums.attachment import AttachmentType
from .attachment import Attachment, ShareAttachmentPayload


class Share(Attachment):
    """
    Вложение с типом "share" (поделиться).

    Attributes:
        title (Optional[str]): Заголовок для шаринга.
        description (Optional[str]): Описание.
        image_url (Optional[str]): URL изображения для предпросмотра.
        payload (Optional[ShareAttachmentPayload]): Данные share-вложения
            (url + token).
    """

    type: Literal[  # pyright: ignore[reportIncompatibleVariableOverride]
        AttachmentType.SHARE
    ]
    title: str | None = None
    description: str | None = None
    image_url: str | None = None
    payload: ShareAttachmentPayload | None = (  # pyright: ignore[reportIncompatibleVariableOverride]
        None
    )
