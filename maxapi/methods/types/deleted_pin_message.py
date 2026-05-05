from pydantic import BaseModel


class DeletedPinMessage(BaseModel):
    """
    Ответ API при удалении закрепленного в чате сообщения.

    Attributes:
        success: Статус успешности операции.
        message: Дополнительное сообщение или ошибка.
    """

    success: bool
    message: str | None = None
