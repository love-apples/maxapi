from pydantic import BaseModel


class PinnedMessage(BaseModel):
    """
    Ответ API при добавлении списка администраторов в чат.

    Attributes:
        success: Статус успешности операции.
        message: Дополнительное сообщение или ошибка.
    """

    success: bool
    message: str | None = None
