from typing import Optional

from pydantic import BaseModel


class DeletedPinMessage(BaseModel):
    """
    Ответ API при удалении закрепленного в чате сообщения.

    Attributes:
        success (bool): Статус успешности операции.
        message (Optional[str]): Дополнительное сообщение или ошибка.
    """

    success: bool
    message: Optional[str] = None
