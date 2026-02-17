from pydantic import BaseModel


class DeletedMessage(BaseModel):
    """
    Ответ API при удалении сообщения.

    Attributes:
        success (bool): Статус успешности операции.
        message (Optional[str]): Дополнительное сообщение или ошибка.
    """

    success: bool
    message: str | None = None
