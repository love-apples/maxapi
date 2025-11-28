from typing import Optional

from pydantic import BaseModel


class DeletedBotFromChat(BaseModel):
    """
    Ответ API при удалении бота из чата.

    Attributes:
        success (bool): Статус успешности операции.
        message (Optional[str]): Дополнительное сообщение или ошибка.
    """

    success: bool
    message: Optional[str] = None
