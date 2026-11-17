"""Тесты получения закреплённого сообщения и устаревшего модуля-псевдонима."""

import importlib
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest
from maxapi.connection.base import BaseConnection
from maxapi.enums.http_method import HTTPMethod
from maxapi.methods.get_pinned_message import GetPinnedMessage
from maxapi.methods.types.getted_pinned_message import GettedPin

CHAT_ID = 100


def _patched_request(return_value=None):
    return patch.object(
        BaseConnection,
        "request",
        new=AsyncMock(
            return_value=Mock() if return_value is None else return_value
        ),
    )


async def test_get_pinned_message_requests_chat_pin_endpoint(bot):
    method = GetPinnedMessage(bot=bot, chat_id=CHAT_ID)

    with _patched_request(GettedPin(message=None)) as mocked_request:
        result = await method.fetch()

    kwargs = mocked_request.call_args.kwargs
    assert kwargs["method"] == HTTPMethod.GET
    assert kwargs["path"] == f"/chats/{CHAT_ID}/pin"
    assert kwargs["model"] is GettedPin
    assert kwargs["params"] == bot.params
    assert isinstance(result, GettedPin)
    assert result.message is None


async def test_get_pinned_message_returns_parsed_message(bot):
    payload = {
        "message": {
            "sender": {
                "user_id": 1,
                "first_name": "Тест",
                "is_bot": False,
                "last_activity_time": 0,
            },
            "recipient": {"chat_id": CHAT_ID, "chat_type": "chat"},
            "timestamp": 1756704000000,
            "body": {"mid": "mid.pinned", "seq": 1, "text": "закреплено"},
        }
    }
    pinned = GettedPin.model_validate(payload)

    with _patched_request(pinned):
        result = await GetPinnedMessage(bot=bot, chat_id=CHAT_ID).fetch()

    assert result.message is not None
    assert result.message.body.mid == "mid.pinned"


async def test_bot_get_pin_message_delegates_to_method(bot):
    expected = GettedPin(message=None)

    with patch.object(
        GetPinnedMessage, "fetch", new=AsyncMock(return_value=expected)
    ) as fetch:
        result = await bot.get_pin_message(CHAT_ID)

    fetch.assert_awaited_once()
    assert result is expected


def test_deprecated_pineed_module_warns_and_reexports():
    module_name = "maxapi.methods.types.getted_pineed_message"
    sys.modules.pop(module_name, None)

    with pytest.warns(DeprecationWarning, match="getted_pinned_message"):
        legacy = importlib.import_module(module_name)

    assert legacy.GettedPin is GettedPin
    assert legacy.__all__ == ["GettedPin"]
