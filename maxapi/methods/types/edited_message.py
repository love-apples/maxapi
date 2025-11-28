from typing import Optional

from pydantic import BaseModel


class EditedMessage(BaseModel):
    """
    Ответ API при изменении сообщения.

    Attributes:
        success (bool): Статус успешности операции.
        message (Optional[str]): Дополнительное сообщение или ошибка.
    """

    success: bool
    message: Optional[str] = None
