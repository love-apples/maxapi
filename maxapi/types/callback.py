from pydantic import BaseModel

from ..types.users import User


class Callback(BaseModel):
    """
    Модель callback-запроса.

    Attributes:
        timestamp: Временная метка callback.
        callback_id: Уникальный идентификатор callback.
        payload: Дополнительные данные callback.
            Может быть None.
        user: Объект пользователя, инициировавшего callback.
    """

    timestamp: int
    callback_id: str
    payload: str | None = None
    user: User
