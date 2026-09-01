from pydantic import BaseModel


class EditedComment(BaseModel):
    """
    Ответ API при изменении комментария.

    Attributes:
        success: Статус успешности операции.
        message: Дополнительное сообщение или ошибка.
    """

    success: bool
    message: str | None = None
