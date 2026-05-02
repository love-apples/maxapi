from pydantic import BaseModel


class EditedMessage(BaseModel):
    """
    Ответ API при изменении сообщения.

    Attributes:
        success: Статус успешности операции.
        message: Дополнительное сообщение или ошибка.
    """

    success: bool
    message: str | None = None
