from typing import Optional

from pydantic import BaseModel


class RemovedMemberChat(BaseModel):
    """
    Ответ API при удалении участника из чата.

    Attributes:
        success (bool): Статус успешности операции.
        message (Optional[str]): Дополнительное сообщение или описание ошибки.
    """

    success: bool
    message: Optional[str] = None
