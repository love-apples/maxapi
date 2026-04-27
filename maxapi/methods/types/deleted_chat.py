from pydantic import BaseModel


class DeletedChat(BaseModel):
    """
    Ответ API при удалении чата (?).

    Attributes:
        success: Статус успешности операции.
        message: Дополнительное сообщение или ошибка.
    """

    success: bool
    message: str | None = None
