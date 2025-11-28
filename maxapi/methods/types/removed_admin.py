from typing import Optional

from pydantic import BaseModel


class RemovedAdmin(BaseModel):
    """
    Ответ API при отмене прав администратора у пользователя в чате

    Attributes:
        success (bool): Статус успешности операции.
        message (Optional[str]): Дополнительное сообщение или ошибка.
    """

    success: bool
    message: Optional[str] = None
