from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ...bot import Bot


class SendedCallback(BaseModel):
    """
    Ответ API после выполнения callback-действия.

    Attributes:
        success: Статус успешности выполнения callback.
        message: Дополнительное сообщение или описание
            ошибки.
        bot: Внутреннее поле для хранения ссылки
            на экземпляр бота (не сериализуется).
    """

    success: bool
    message: str | None = None
    bot: Any | None = Field(default=None, exclude=True)

    if TYPE_CHECKING:
        bot: Bot | None  # type: ignore
