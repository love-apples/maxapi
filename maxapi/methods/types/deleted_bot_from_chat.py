from pydantic import BaseModel


class DeletedBotFromChat(BaseModel):
    """
    Ответ API при удалении бота из чата.

    Attributes:
        success: Статус успешности операции.
        message: Дополнительное сообщение или ошибка.
    """

    success: bool
    message: str | None = None
