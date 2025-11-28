from typing import Optional

from pydantic import BaseModel


class BotCommand(BaseModel):
    """
    Модель команды бота для сериализации.

    Attributes:
        name (str): Название команды.
        description (Optional[str]): Описание команды. Может быть None.
    """

    name: str
    description: Optional[str] = None
