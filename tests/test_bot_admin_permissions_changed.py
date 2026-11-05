"""Тесты события bot_admin_permissions_changed.

Покрывает:
  - парсинг payload из OpenAPI-схемы через UpdateUnionAdapter;
  - обогащение события (chat, from_user) с auto_requests и без;
  - диспетчеризацию через @dp.bot_admin_permissions_changed;
  - подписку на событие через Webhook.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from maxapi.enums.chat_permission import ChatPermission
from maxapi.enums.update import UpdateType
from maxapi.exceptions.max import MaxApiError
from maxapi.methods.subscribe_webhook import SubscribeWebhook
from maxapi.types.fetchable import ChatRef, FromUserRef
from maxapi.types.updates import UpdateUnionAdapter
from maxapi.types.updates.bot_admin_permissions_changed import (
    BotAdminPermissionsChanged,
)
from maxapi.utils.updates import enrich_event
from pydantic import ValidationError

from tests.conftest import setup_dispatcher_for_handle

PAYLOAD = {
    "update_type": "bot_admin_permissions_changed",
    "timestamp": 1_700_000_000_000,
    "chat_id": -70001,
    "user_id": 42,
    "bot_id": 100500,
    "is_channel": True,
    "is_admin": True,
    "permissions": ["read_all_messages", "write", "delete"],
}


class TestParsing:
    """Payload из схемы парсится в BotAdminPermissionsChanged."""

    def test_full_payload(self):
        event = UpdateUnionAdapter.validate_python(PAYLOAD)

        assert isinstance(event, BotAdminPermissionsChanged)
        assert event.update_type == UpdateType.BOT_ADMIN_PERMISSIONS_CHANGED
        assert event.permissions == [
            ChatPermission.READ_ALL_MESSAGES,
            ChatPermission.WRITE,
            ChatPermission.DELETE,
        ]
        assert event.get_ids() == (-70001, 42)

    @pytest.mark.parametrize("permissions", [None, "missing"])
    def test_permissions_optional(self, permissions):
        payload = {**PAYLOAD, "is_admin": False}
        if permissions == "missing":
            payload.pop("permissions")
        else:
            payload["permissions"] = permissions

        event = UpdateUnionAdapter.validate_python(payload)

        assert event.is_admin is False
        assert event.permissions is None

    @pytest.mark.parametrize(
        "field", ["chat_id", "user_id", "bot_id", "is_channel", "is_admin"]
    )
    def test_required_fields(self, field):
        payload = {k: v for k, v in PAYLOAD.items() if k != field}

        with pytest.raises(ValidationError):
            UpdateUnionAdapter.validate_python(payload)


class TestEnrich:
    """enrich_event для bot_admin_permissions_changed."""

    async def test_resolves_chat_and_changer(
        self, bot, fixture_bot_admin_permissions_changed
    ):
        event = fixture_bot_admin_permissions_changed
        fake_chat, member = MagicMock(), MagicMock()
        bot.get_chat_by_id = AsyncMock(return_value=fake_chat)
        bot.get_chat_member = AsyncMock(return_value=member)

        result = await enrich_event(event, bot)

        bot.get_chat_by_id.assert_awaited_once_with(event.chat_id)
        bot.get_chat_member.assert_awaited_once_with(
            chat_id=event.chat_id, user_id=event.user_id
        )
        assert result.chat is fake_chat
        assert result.from_user is member

    async def test_member_error_is_logged(
        self, bot, fixture_bot_admin_permissions_changed, caplog
    ):
        bot.get_chat_by_id = AsyncMock(return_value=MagicMock())
        bot.get_chat_member = AsyncMock(
            side_effect=MaxApiError(code=403, raw={"message": "forbidden"})
        )

        result = await enrich_event(fixture_bot_admin_permissions_changed, bot)

        assert result.from_user is None
        assert "Не удалось получить участника" in caplog.text

    async def test_auto_requests_false_builds_lazy_refs(
        self, bot, fixture_bot_admin_permissions_changed
    ):
        event = fixture_bot_admin_permissions_changed
        bot.auto_requests = False
        bot.get_chat_by_id = AsyncMock()
        bot.get_chat_member = AsyncMock()

        result = await enrich_event(event, bot)

        bot.get_chat_by_id.assert_not_called()
        bot.get_chat_member.assert_not_called()
        assert isinstance(result.chat, ChatRef)
        assert isinstance(result.from_user, FromUserRef)


class TestDispatch:
    """Хендлер @dp.bot_admin_permissions_changed получает событие."""

    async def test_handler_called(
        self, dispatcher, bot, fixture_bot_admin_permissions_changed
    ):
        handled = []

        @dispatcher.bot_admin_permissions_changed()
        async def _handler(event):
            handled.append(event)

        @dispatcher.bot_added()
        async def _other(event):  # pragma: no cover
            handled.append("wrong")

        setup_dispatcher_for_handle(dispatcher, bot)
        await dispatcher.handle(fixture_bot_admin_permissions_changed)

        assert handled == [fixture_bot_admin_permissions_changed]


def test_webhook_subscription_accepts_update_type(bot):
    method = SubscribeWebhook(
        bot=bot,
        url="https://example.com/hook",
        update_types=[UpdateType.BOT_ADMIN_PERMISSIONS_CHANGED],
    )

    assert method.update_types == ["bot_admin_permissions_changed"]
