from typing import Literal

from ...enums.attachment import AttachmentType
from .attachment import Attachment, ShareAttachmentPayload
from .url_str import UrlStr


class Share(Attachment):
    """
    Вложение с типом "share" (поделиться).

    Attributes:
        title: Заголовок для шаринга.
        description: Описание.
        image_url: URL изображения для предпросмотра.
        payload: Данные share-вложения
            (url + token).
    """

    type: Literal[  # pyright: ignore[reportIncompatibleVariableOverride]
        AttachmentType.SHARE
    ]
    title: str | None = None
    description: str | None = None
    image_url: UrlStr | str | None = None
    payload: ShareAttachmentPayload | None = (  # pyright: ignore[reportIncompatibleVariableOverride]
        None
    )
