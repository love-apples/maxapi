from typing import Optional

from pydantic import BaseModel


class Unsubscribed(BaseModel):
    """
    Результат отписки от обновлений на Webhook

    Attributes:
        success (bool): Статус успешности операции.
        message (Optional[str]): Дополнительное сообщение или ошибка.
    """

    success: bool
    message: Optional[str] = None
