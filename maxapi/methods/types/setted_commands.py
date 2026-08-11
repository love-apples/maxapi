from pydantic import BaseModel

from ...types.command import BotCommand


class SettedCommands(BaseModel):
    """
    Результат редактирования команд бота

    Attributes:
        commands: Команды, которые поддерживает бот
            (до 32 элементов).
    """

    commands: list[BotCommand] | None = None
