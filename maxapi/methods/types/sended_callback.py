from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ...bot import Bot


class SendedCallback(BaseModel):
    """
    Ответ API после выполнения callback-действия.

    Attributes:
        success (bool): Статус успешности выполнения callback.
        message (Optional[str]): Дополнительное сообщение или описание ошибки.
        bot (Optional[Bot]): Внутреннее поле для хранения ссылки на экземпляр бота (не сериализуется).
    """

    success: bool
    message: Optional[str] = None
    bot: Optional[Any] = Field(default=None, exclude=True)  # pyright: ignore[reportRedeclaration]

    if TYPE_CHECKING:
        bot: Optional[Bot]  # type: ignore
