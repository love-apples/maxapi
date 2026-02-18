from pydantic import BaseModel


class AddedMembersChat(BaseModel):
    """
    Ответ API при добавлении списка пользователей в чат.

    Attributes:
        success (bool): Статус успешности операции.
        message (Optional[str]): Дополнительное сообщение или ошибка.
    """

    success: bool
    message: str | None = None
