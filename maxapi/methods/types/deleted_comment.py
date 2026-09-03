from pydantic import BaseModel


class DeletedComment(BaseModel):
    """
    Ответ API при удалении комментария.

    Attributes:
        success: Статус успешности операции.
        message: Дополнительное сообщение или ошибка.
    """

    success: bool
    message: str | None = None
