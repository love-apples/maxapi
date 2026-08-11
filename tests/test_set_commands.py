"""Тесты метода SetCommands (PATCH /me/commands)."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from maxapi.connection.base import BaseConnection
from maxapi.enums.api_path import ApiPath
from maxapi.enums.http_method import HTTPMethod
from maxapi.methods.set_commands import SetCommands
from maxapi.methods.types.setted_commands import SettedCommands
from maxapi.types.command import BotCommand


async def test_set_commands_fetch_sends_patch_to_me_commands(bot):
    """Запрос уходит методом PATCH на /me/commands."""
    method = SetCommands(
        bot=bot,
        commands=[BotCommand(name="/start", description="Запуск")],
    )

    with patch.object(
        BaseConnection, "request", new=AsyncMock(return_value=Mock())
    ) as mocked_request:
        await method.fetch()

    kwargs = mocked_request.call_args.kwargs
    assert kwargs["method"] == HTTPMethod.PATCH
    assert kwargs["path"] == "/me/commands"
    assert kwargs["json"] == {
        "commands": [{"name": "/start", "description": "Запуск"}]
    }


async def test_set_commands_fetch_skips_empty_description(bot):
    """Команда без описания уходит без ключа description."""
    method = SetCommands(bot=bot, commands=[BotCommand(name="/start")])

    with patch.object(
        BaseConnection, "request", new=AsyncMock(return_value=Mock())
    ) as mocked_request:
        await method.fetch()

    assert mocked_request.call_args.kwargs["json"] == {
        "commands": [{"name": "/start"}]
    }


async def test_set_commands_fetch_sends_empty_list_to_delete(bot):
    """Пустой список команд уходит как есть и удаляет все команды."""
    method = SetCommands(bot=bot, commands=[])

    with patch.object(
        BaseConnection, "request", new=AsyncMock(return_value=Mock())
    ) as mocked_request:
        await method.fetch()

    assert mocked_request.call_args.kwargs["json"] == {"commands": []}


def test_set_commands_rejects_more_than_32_commands(bot):
    """Больше 32 команд API не принимает — проверяем до запроса."""
    commands = [BotCommand(name=f"/cmd{i}") for i in range(33)]

    with pytest.raises(ValueError, match="32"):
        SetCommands(bot=bot, commands=commands)


async def test_bot_set_commands_returns_model(bot):
    """bot.set_commands проксирует вызов и возвращает модель ответа."""
    expected = SettedCommands(commands=[BotCommand(name="/start")])

    with patch.object(
        BaseConnection, "request", new=AsyncMock(return_value=expected)
    ) as mocked_request:
        result = await bot.set_commands(BotCommand(name="/start"))

    assert result is expected
    assert mocked_request.call_args.kwargs["path"] == "/me/commands"


async def test_bot_set_commands_without_arguments_clears_commands(bot):
    """Вызов без аргументов отправляет пустой список команд."""
    with patch.object(
        BaseConnection, "request", new=AsyncMock(return_value=Mock())
    ) as mocked_request:
        await bot.set_commands()

    assert mocked_request.call_args.kwargs["json"] == {"commands": []}


async def test_bot_set_my_commands_is_deprecated(bot):
    """Старый метод предупреждает об отключении PATCH /me."""
    with (
        patch.object(
            BaseConnection, "request", new=AsyncMock(return_value=Mock())
        ) as mocked_request,
        pytest.deprecated_call(match="set_commands"),
    ):
        await bot.set_my_commands(BotCommand(name="/start"))

    assert mocked_request.call_args.kwargs["path"] == ApiPath.ME
