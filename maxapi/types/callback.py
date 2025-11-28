from typing import Optional

from pydantic import BaseModel

from ..types.users import User


class Callback(BaseModel):
    """
    Модель callback-запроса.

    Attributes:
        timestamp (int): Временная метка callback.
        callback_id (str): Уникальный идентификатор callback.
        payload (Optional[str]): Дополнительные данные callback. Может быть None.
        user (User): Объект пользователя, инициировавшего callback.
    """

    timestamp: int
    callback_id: str
    payload: Optional[str] = None
    user: User
