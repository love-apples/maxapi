from typing import Optional

from pydantic import BaseModel


class Subscribed(BaseModel):
    """
    Результат подписки на обновления на Webhook

    Attributes:
        success (bool): Статус успешности операции.
        message (Optional[str]): Дополнительное сообщение или ошибка.
    """

    success: bool
    message: Optional[str] = None
