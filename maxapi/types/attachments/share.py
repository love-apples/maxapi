from typing import Literal, Optional

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
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
