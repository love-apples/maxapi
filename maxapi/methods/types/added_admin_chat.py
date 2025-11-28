from typing import Optional

from pydantic import BaseModel


class AddedListAdminChat(BaseModel):
    """
    Ответ API при добавлении списка администраторов в чат.

    Attributes:
        success (bool): Статус успешности операции.
        message (Optional[str]): Дополнительное сообщение или ошибка.
    """

    success: bool
    message: Optional[str] = None
