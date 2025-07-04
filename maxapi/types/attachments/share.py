from typing import Literal, Optional

from .attachment import Attachment


class Share(Attachment):
    
    """
    Вложение с типом "share" (поделиться).

    Attributes:
        type (Literal['share']): Тип вложения, всегда 'share'.
        title (Optional[str]): Заголовок для шаринга.
        description (Optional[str]): Описание.
        image_url (Optional[str]): URL изображения для предпросмотра.
    """
    
    type: Literal['share'] = 'share'
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
