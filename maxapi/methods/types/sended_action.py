from pydantic import BaseModel


class SendedAction(BaseModel):
    """
    Ответ API после выполнения действия.

    Attributes:
        success: Статус успешности выполнения операции.
        message: Дополнительное сообщение или описание ошибки.
    """

    success: bool
    message: str | None = None
