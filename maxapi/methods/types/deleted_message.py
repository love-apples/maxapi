from pydantic import BaseModel


class DeletedMessage(BaseModel):
    """
    Ответ API при удалении сообщения.

    Attributes:
        success: Статус успешности операции.
        message: Дополнительное сообщение или ошибка.
    """

    success: bool
    message: str | None = None
