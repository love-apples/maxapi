from pydantic import BaseModel


class Unsubscribed(BaseModel):
    """
    Результат отписки от обновлений на Webhook

    Attributes:
        success: Статус успешности операции.
        message: Дополнительное сообщение или ошибка.
    """

    success: bool
    message: str | None = None
