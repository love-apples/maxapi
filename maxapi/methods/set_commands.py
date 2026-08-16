"""Метод изменения списка команд бота (PATCH /me/commands)."""

from typing import TYPE_CHECKING, Any, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..methods.types.setted_commands import SettedCommands

if TYPE_CHECKING:
    from ..bot import Bot
    from ..types.command import BotCommand


class SetCommands(BaseConnection):
    """
    Класс для добавления, изменения и удаления команд бота.

    https://dev.max.ru/docs-api/methods/PATCH/me/commands

    Attributes:
        bot: Экземпляр бота для выполнения запроса.
        commands: Команды, которые поддерживает бот
            (до 32 элементов). Пустой список удаляет все команды
            бота, None оставляет их без изменений.
    """

    def __init__(
        self,
        bot: "Bot",
        commands: "list[BotCommand] | None" = None,
    ):
        if commands is not None and len(commands) > 32:
            raise ValueError("commands не может содержать больше 32 элементов")

        super().__init__()
        self.bot = bot
        self.commands = commands

    async def fetch(self) -> SettedCommands:
        """
        Отправляет запрос на изменение списка команд бота.

        Returns:
            SettedCommands: Актуальный список команд бота
        """

        bot = self._ensure_bot()

        json: dict[str, Any] = {}

        if self.commands is not None:
            json["commands"] = [
                command.model_dump(exclude_none=True)
                for command in self.commands
            ]

        response = await super().request(
            method=HTTPMethod.PATCH,
            path=ApiPath.ME.value + ApiPath.COMMANDS,
            model=SettedCommands,
            params=bot.params,
            json=json,
        )

        return cast(SettedCommands, response)
