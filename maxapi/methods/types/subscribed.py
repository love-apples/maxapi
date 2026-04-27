from pydantic import BaseModel


class Subscribed(BaseModel):
    """
    Результат подписки на обновления на Webhook

    Attributes:
        success: Статус успешности операции.
        message: Дополнительное сообщение или ошибка.
    """

    success: bool
    message: str | None = None
