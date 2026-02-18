from pydantic import BaseModel


class DeletedChat(BaseModel):
    """
    Ответ API при удалении чата (?).

    Attributes:
        success (bool): Статус успешности операции.
        message (Optional[str]): Дополнительное сообщение или ошибка.
    """

    success: bool
    message: str | None = None
