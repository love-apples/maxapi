from pydantic import BaseModel


class BotCommand(BaseModel):
    """
    Модель команды бота для сериализации.

    Attributes:
        name: Название команды.
        description: Описание команды. Может быть None.
    """

    name: str
    description: str | None = None
