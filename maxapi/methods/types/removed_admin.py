from pydantic import BaseModel


class RemovedAdmin(BaseModel):
    """
    Ответ API при отмене прав администратора у пользователя в чате

    Attributes:
        success: Статус успешности операции.
        message: Дополнительное сообщение или ошибка.
    """

    success: bool
    message: str | None = None
