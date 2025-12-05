from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

from ..filters.filter import BaseFilter
from ..types.updates import UpdateUnion
from ..types.updates.message_created import MessageCreated


@dataclass
class CommandsInfo:
    """
    Датакласс информации о командах

    Attributes:
        commands (List[str]): Список команд
        info (Optional[str]): Информация о их предназначениях
    """

    commands: List[str]
    info: Optional[str] = None


class Command(BaseFilter):
    """
    Фильтр сообщений на соответствие команде.

    Args:
        commands (str | List[str]): Ожидаемая команда или список команд без префикса.
        prefix (str, optional): Префикс команды (по умолчанию '/').
        check_case (bool, optional): Учитывать регистр при сравнении (по умолчанию False).
        ignore_symbol_at_sign (bool, optional): Учитывать символ "@" при отправке команды с упоминанием бота (по умолчанию False).
        only_with_bot_username (bool, optional): Обязательно упоминать бота при отправке команды (по умолчанию False).
    """

    def __init__(
        self,
        commands: str | List[str],
        prefix: str = "/",
        check_case: bool = False,
        ignore_symbol_at_sign: bool = False,
        only_with_bot_username: bool = False,
    ):
        """
        Инициализация фильтра команд.
        """

        if isinstance(commands, str):
            self.commands = [commands]
        else:
            self.commands = commands

        self.prefix = prefix
        self.check_case = check_case
        self.ignore_symbol_at_sign = ignore_symbol_at_sign
        self.only_with_bot_username = only_with_bot_username

        if not check_case:
            self.commands = [cmd.lower() for cmd in self.commands]

    def parse_command(
        self, text: str, bot_username: str
    ) -> Tuple[str, List[str]]:
        """
        Извлекает команду из текста.

        Args:
            text (str): Текст сообщения.
            bot_username (str): Имя пользователя бота.

        Returns:
            Tuple[str, List[str]]: Кортеж из команды без префикса и списка аргументов,
            либо ('', []) если команда не найдена или текст не соответствует формату.
        """

        if not text.strip():
            return "", []

        args = text.split()

        if not args:
            return "", []

        first = args[0]

        if self.ignore_symbol_at_sign:
            if first == bot_username:
                first = "@" + first

        if first.startswith("@"):
            if len(args) < 2:
                return "", []

            if not first[1:] == bot_username:
                return "", []

            command_part = args[1]

            if not command_part.startswith(self.prefix):
                return "", []

            command = command_part[len(self.prefix) :]
            arguments = args[2:]

        else:
            if self.only_with_bot_username:
                return "", []

            command_part = first

            if not command_part.startswith(self.prefix):
                return "", []

            command = command_part[len(self.prefix) :]
            arguments = args[1:]

        return command, arguments

    async def __call__(
        self, event: UpdateUnion
    ) -> Union[Dict[str, List[str]], bool]:
        """
        Проверяет, соответствует ли сообщение заданной(ым) команде(ам).

        Args:
            event (MessageCreated): Событие сообщения.

        Returns:
            dict | bool: dict с аргументами команды при совпадении, иначе False.
        """

        if not isinstance(event, MessageCreated):
            return False

        text = event.message.body.text

        if not text:
            return False

        # временно
        bot_me = event._ensure_bot().me
        bot_username = ""
        if bot_me:
            bot_username = bot_me.username or ""

        parsed_command, args = self.parse_command(text, bot_username)
        if not parsed_command:
            return False

        if not self.check_case:
            if parsed_command.lower() in [
                commands.lower() for commands in self.commands
            ]:
                return {"args": args}
            else:
                return False

        if parsed_command in self.commands:
            return {"args": args}

        return False


class CommandStart(Command):
    """
    Фильтр для команды /start.

    Args:
        prefix (str, optional): Префикс команды (по умолчанию '/').
        check_case (bool, optional): Учитывать регистр (по умолчанию False)
        ignore_symbol_at_sign (bool, optional): Учитывать символ "@" при отправке команды с упоминанием бота (по умолчанию False).
        only_with_bot_username (bool, optional): Обязательно упоминать бота при отправке команды (по умолчанию False)..
    """

    def __init__(
        self,
        prefix="/",
        check_case=False,
        ignore_symbol_at_sign: bool = False,
        only_with_bot_username: bool = False,
    ):
        super().__init__(
            "start",
            prefix,
            check_case,
            ignore_symbol_at_sign,
            only_with_bot_username,
        )

    async def __call__(self, event):
        return await super().__call__(event)
