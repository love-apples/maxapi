from typing import Literal

from ...enums.attachment import AttachmentType
from .attachment import Attachment


class Share(Attachment):
    """
    Вложение с типом "share" (поделиться).

    Attributes:
        title (Optional[str]): Заголовок для шаринга.
        description (Optional[str]): Описание.
        image_url (Optional[str]): URL изображения для предпросмотра.
    """

    type: Literal[  # pyright: ignore[reportIncompatibleVariableOverride]
        AttachmentType.SHARE
    ]
    title: str | None = None
    description: str | None = None
    image_url: str | None = None
