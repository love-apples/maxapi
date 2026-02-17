from pydantic import BaseModel


class SendedAction(BaseModel):
    """
    Ответ API после выполнения действия.

    Attributes:
        success (bool): Статус успешности выполнения операции.
        message (Optional[str]): Дополнительное сообщение или описание ошибки.
    """

    success: bool
    message: str | None = None
