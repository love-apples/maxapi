from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from ..filters.filter import BaseFilter
from ..filters.middleware import BaseMiddleware
from ..types.updates.message_created import MessageCreated


def parse_command(
    text: str, prefix: str
) -> tuple[str | None, str, list[str]] | None:
    """
    Распарсить строку-команду.

    Формат: [@<bot_username>] <prefix><command> [<arg>...]

    Args:
        text: Текст сообщения.
        prefix: Префикс команды.

    Returns:
        Кортеж, состоящий из ника бота, команды и списка аргументов, или None,
            если строка не соответствует формату команды.
    """
    match text.split(maxsplit=2):
        case [a] if a.startswith(prefix):
            return None, a, []
        case [a, b] if a.startswith(prefix):
            return None, a, b.split()
        case [a, b] if a.startswith("@") and b.startswith(prefix):
            return a, b, []
        case [a, b, c] if a.startswith("@") and b.startswith(prefix):
            return a, b, c.split()
        case _:
            return None

class IsCommand(BaseFilter):
    """
    Фильтр сообщений на соответствие команде.

    Args:
        *commands: Ожидаемая команда или команды без префикса.
        prefix: Префикс команды (по умолчанию '/').
        check_case: Учитывать регистр при сравнении (по
            умолчанию False).
        only_with_bot_username: Обязательно упоминать бота при
            отправке команды (по умолчанию False).
    """

    __slots__ = ("commands", "prefix", "check_case", "only_with_bot_username")

    def __init__(
        self,
        *commands: str,
        prefix: str = "/",
        check_case: bool = False,
        only_with_bot_username: bool = False,
    ):
        """
        Инициализация фильтра команд.
        """
        if check_case:
            self.commands = {*commands}
        else:
            self.commands = {c.lower() for c in commands}
        self.prefix = prefix
        self.check_case = check_case
        self.only_with_bot_username = only_with_bot_username

    def __call__(
        self, event: MessageCreated
    ) -> bool:
        """
        Проверяет, соответствует ли сообщение заданной(ым) команде(ам).

        Args:
            event: Событие сообщения.
        """
        if (text := event.message.body.text) is None:
            return False

        text = text.strip()

        if self.check_case:
            text = text.lower()

        if self.only_with_bot_username:
            bot_me = event._ensure_bot().me
            bot_username = bot_me.username or "" if bot_me else ""
            bot_username = f"@{bot_username}"
            if not text.startswith(bot_username):
                return False
            command, *_ = text.split(maxsplit=2)[1:]
        else:
            command, *_ = text.split(maxsplit=2)

        if command.removeprefix(self.prefix) in self.commands:
            return True

        return False

class ProvideCommand(BaseMiddleware):
    __slots__ = ("prefix",)

    def __init__(self, prefix: str = "/"):
        self.prefix = prefix

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event_object: Any,
        data: dict[str, Any],
    ) -> Any:
        if parsed := parse_command(
            event_object.message.body.text.strip(),
            self.prefix
        ):
            data["args"] = parsed[2]
        return await handler(event_object, data)

def Command(
    *commands,
    prefix: str = "/",
    check_case: bool = False,
    only_with_bot_username: bool = False,
) -> tuple[IsCommand, ProvideCommand]:
    return (
        IsCommand(
            *commands,
            prefix=prefix,
            check_case=check_case,
            only_with_bot_username=only_with_bot_username
        ),
        ProvideCommand(prefix=prefix)
    )

def CommandStart(**kwargs) -> tuple[IsCommand, ProvideCommand]:
    return Command("start", **kwargs)

@dataclass(slots=True)
class CommandsInfo:
    """
    Датакласс информации о командах

    Attributes:
        commands: Список команд
        info: Информация о их предназначениях
    """

    commands: list[str]
    info: str | None = None
