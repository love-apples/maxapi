from pydantic import BaseModel


class RemovedMemberChat(BaseModel):
    """
    Ответ API при удалении участника из чата.

    Attributes:
        success: Статус успешности операции.
        message: Дополнительное сообщение или описание ошибки.
    """

    success: bool
    message: str | None = None
