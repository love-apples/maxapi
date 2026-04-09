"""Тесты для maxapi/utils/updates.py.

Покрывает:
  - _resolve_chat   : все ветки разрешения chat_id
  - _resolve_from_user : все ветки определения отправителя
  - _inject_bot     : внедрение ссылки на бота
  - enrich_event    : сквозной пайплайн + auto_requests=False
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from maxapi.enums.chat_type import ChatType
from maxapi.utils.updates import (
    _inject_bot,
    _resolve_chat,
    _resolve_from_user,
    enrich_event,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chat(chat_type: ChatType = ChatType.CHAT):
    chat = MagicMock()
    chat.type = chat_type
    return chat


# ===========================================================================
# _resolve_chat
# ===========================================================================


class TestResolveChat:
    """Юнит-тесты для _resolve_chat."""

    async def test_bot_removed_never_fetches_chat(
        self, bot, fixture_bot_removed
    ):
        """
        BotRemoved всегда пропускает загрузку чата,
        независимо от is_channel.
        """
        bot.get_chat_by_id = AsyncMock()

        for is_channel in (True, False):
            fixture_bot_removed.is_channel = is_channel
            fixture_bot_removed.chat = None
            await _resolve_chat(fixture_bot_removed, bot)

        bot.get_chat_by_id.assert_not_called()
        assert fixture_bot_removed.chat is None

    async def test_dialog_removed_never_fetches_chat(
        self, bot, fixture_dialog_removed
    ):
        """DialogRemoved всегда пропускает загрузку чата."""
        bot.get_chat_by_id = AsyncMock()

        await _resolve_chat(fixture_dialog_removed, bot)

        bot.get_chat_by_id.assert_not_called()
        assert fixture_dialog_removed.chat is None

    async def test_event_with_top_level_chat_id_fetches_chat(
        self, bot, fixture_bot_started
    ):
        """События с chat_id на верхнем уровне загружают чат по нему."""
        fake_chat = _make_chat()
        bot.get_chat_by_id = AsyncMock(return_value=fake_chat)

        await _resolve_chat(fixture_bot_started, bot)

        bot.get_chat_by_id.assert_awaited_once_with(
            fixture_bot_started.chat_id
        )
        assert fixture_bot_started.chat is fake_chat

    async def test_message_created_falls_back_to_recipient_chat_id(
        self, bot, fixture_message_created
    ):
        """MessageCreated не имеет top-level chat_id — берётся из recipient."""
        fake_chat = _make_chat()
        bot.get_chat_by_id = AsyncMock(return_value=fake_chat)

        await _resolve_chat(fixture_message_created, bot)

        expected_chat_id = fixture_message_created.message.recipient.chat_id
        bot.get_chat_by_id.assert_awaited_once_with(expected_chat_id)
        assert fixture_message_created.chat is fake_chat

    async def test_message_created_no_chat_id_anywhere_skips_fetch(
        self, bot, fixture_message_created
    ):
        """Если recipient.chat_id = None — get_chat_by_id не вызывается."""
        fixture_message_created.message.recipient.chat_id = None
        bot.get_chat_by_id = AsyncMock()

        await _resolve_chat(fixture_message_created, bot)

        bot.get_chat_by_id.assert_not_called()
        assert fixture_message_created.chat is None

    async def test_message_edited_falls_back_to_recipient_chat_id(
        self, bot, fixture_message_edited
    ):
        """MessageEdited аналогично MessageCreated."""
        fake_chat = _make_chat()
        bot.get_chat_by_id = AsyncMock(return_value=fake_chat)

        await _resolve_chat(fixture_message_edited, bot)

        expected_chat_id = fixture_message_edited.message.recipient.chat_id
        bot.get_chat_by_id.assert_awaited_once_with(expected_chat_id)

    async def test_message_callback_falls_back_to_recipient_chat_id(
        self, bot, fixture_message_callback
    ):
        """MessageCallback берёт chat_id из message.recipient."""
        fake_chat = _make_chat()
        bot.get_chat_by_id = AsyncMock(return_value=fake_chat)

        await _resolve_chat(fixture_message_callback, bot)

        expected_chat_id = fixture_message_callback.message.recipient.chat_id
        bot.get_chat_by_id.assert_awaited_once_with(expected_chat_id)

    async def test_message_callback_none_message_skips_fetch(
        self, bot, fixture_message_callback
    ):
        """Если message=None — get_chat_by_id не вызывается."""
        fixture_message_callback.message = None
        bot.get_chat_by_id = AsyncMock()

        await _resolve_chat(fixture_message_callback, bot)

        bot.get_chat_by_id.assert_not_called()


# ===========================================================================
# _resolve_from_user
# ===========================================================================


class TestResolveFromUser:
    """Юнит-тесты для _resolve_from_user."""

    async def test_message_created_sets_sender(
        self, bot, fixture_message_created
    ):
        await _resolve_from_user(fixture_message_created, bot)
        assert (
            fixture_message_created.from_user
            is fixture_message_created.message.sender
        )

    async def test_message_edited_sets_sender(
        self, bot, fixture_message_edited
    ):
        await _resolve_from_user(fixture_message_edited, bot)
        assert (
            fixture_message_edited.from_user
            is fixture_message_edited.message.sender
        )

    async def test_message_callback_sets_callback_user(
        self, bot, fixture_message_callback
    ):
        await _resolve_from_user(fixture_message_callback, bot)
        assert (
            fixture_message_callback.from_user
            is fixture_message_callback.callback.user
        )

    async def test_message_removed_chat_type_fetches_member(
        self, bot, fixture_message_removed
    ):
        """CHAT-тип — from_user берётся через get_chat_member(user_id)."""
        fake_chat = _make_chat(ChatType.CHAT)
        fake_member = MagicMock()
        fixture_message_removed.chat = fake_chat
        bot.get_chat_member = AsyncMock(return_value=fake_member)

        await _resolve_from_user(fixture_message_removed, bot)

        bot.get_chat_member.assert_awaited_once_with(
            chat_id=fixture_message_removed.chat_id,
            user_id=fixture_message_removed.user_id,
        )
        assert fixture_message_removed.from_user is fake_member

    async def test_message_removed_dialog_type_sets_chat(
        self, bot, fixture_message_removed
    ):
        """DIALOG-тип — from_user = chat."""
        fake_chat = _make_chat(ChatType.DIALOG)
        fixture_message_removed.chat = fake_chat
        bot.get_chat_member = AsyncMock()

        await _resolve_from_user(fixture_message_removed, bot)

        bot.get_chat_member.assert_not_called()
        assert fixture_message_removed.from_user is fake_chat

    async def test_message_removed_no_chat_skips_from_user(
        self, bot, fixture_message_removed
    ):
        """Если chat=None — from_user не устанавливается."""
        fixture_message_removed.chat = None
        bot.get_chat_member = AsyncMock()

        await _resolve_from_user(fixture_message_removed, bot)

        bot.get_chat_member.assert_not_called()
        assert fixture_message_removed.from_user is None

    async def test_message_removed_get_chat_member_max_api_error_swallowed(
        self, bot, fixture_message_removed
    ):
        """MaxApiError из get_chat_member логируется, событие не падает."""
        from maxapi.exceptions.max import MaxApiError

        fake_chat = _make_chat(ChatType.CHAT)
        fixture_message_removed.chat = fake_chat
        bot.get_chat_member = AsyncMock(
            side_effect=MaxApiError(code=403, raw={"error": "Forbidden"})
        )

        await _resolve_from_user(fixture_message_removed, bot)

        bot.get_chat_member.assert_awaited_once()
        assert fixture_message_removed.from_user is None

    async def test_message_removed_get_chat_member_max_connection_swallowed(
        self, bot, fixture_message_removed
    ):
        """MaxConnection из get_chat_member логируется, событие не падает."""
        from maxapi.exceptions.max import MaxConnection

        fake_chat = _make_chat(ChatType.CHAT)
        fixture_message_removed.chat = fake_chat
        bot.get_chat_member = AsyncMock(
            side_effect=MaxConnection("connection refused")
        )

        await _resolve_from_user(fixture_message_removed, bot)

        bot.get_chat_member.assert_awaited_once()
        assert fixture_message_removed.from_user is None

    async def test_user_removed_with_admin_id_fetches_member(
        self, bot, fixture_user_removed
    ):
        fake_member = MagicMock()
        fixture_user_removed.admin_id = 9999
        bot.get_chat_member = AsyncMock(return_value=fake_member)

        await _resolve_from_user(fixture_user_removed, bot)

        bot.get_chat_member.assert_awaited_once_with(
            chat_id=fixture_user_removed.chat_id,
            user_id=fixture_user_removed.admin_id,
        )
        assert fixture_user_removed.from_user is fake_member

    async def test_user_removed_without_admin_id_skips_member(
        self, bot, fixture_user_removed
    ):
        fixture_user_removed.admin_id = None
        bot.get_chat_member = AsyncMock()

        await _resolve_from_user(fixture_user_removed, bot)

        bot.get_chat_member.assert_not_called()
        assert fixture_user_removed.from_user is None

    async def test_user_removed_get_chat_member_max_api_error_swallowed(
        self, bot, fixture_user_removed
    ):
        """MaxApiError из get_chat_member логируется, событие не падает."""
        from maxapi.exceptions.max import MaxApiError

        fixture_user_removed.admin_id = 9999
        bot.get_chat_member = AsyncMock(
            side_effect=MaxApiError(code=403, raw={"error": "Forbidden"})
        )

        await _resolve_from_user(fixture_user_removed, bot)

        bot.get_chat_member.assert_awaited_once()
        assert fixture_user_removed.from_user is None

    async def test_user_removed_get_chat_member_max_connection_swallowed(
        self, bot, fixture_user_removed
    ):
        """MaxConnection из get_chat_member логируется, событие не падает."""
        from maxapi.exceptions.max import MaxConnection

        fixture_user_removed.admin_id = 9999
        bot.get_chat_member = AsyncMock(
            side_effect=MaxConnection("connection refused")
        )

        await _resolve_from_user(fixture_user_removed, bot)

        bot.get_chat_member.assert_awaited_once()
        assert fixture_user_removed.from_user is None

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "fixture_user_added",
            "fixture_bot_added",
            "fixture_bot_removed",
            "fixture_bot_started",
            "fixture_bot_stopped",
            "fixture_chat_title_changed",
            "fixture_dialog_cleared",
            "fixture_dialog_muted",
            "fixture_dialog_unmuted",
            "fixture_dialog_removed",
        ],
    )
    async def test_events_with_user_attr_set_from_user(
        self, request, bot, fixture_name
    ):
        """Все типы из _EVENTS_WITH_USER_ATTR получают from_user = user."""
        event = request.getfixturevalue(fixture_name)
        await _resolve_from_user(event, bot)
        assert event.from_user is event.user


# ===========================================================================
# _inject_bot
# ===========================================================================


class TestInjectBot:
    """Юнит-тесты для _inject_bot."""

    def test_sets_bot_on_message(self, bot, fixture_message_created):
        _inject_bot(fixture_message_created, bot)
        assert fixture_message_created.message.bot is bot

    def test_sets_bot_on_event(self, bot, fixture_bot_started):
        _inject_bot(fixture_bot_started, bot)
        assert fixture_bot_started.bot is bot

    def test_sets_bot_on_attachment_with_bot_attr(
        self, bot, fixture_message_created
    ):
        att_with_bot = MagicMock(spec=["bot"])
        att_without_bot = MagicMock(spec=[])
        fixture_message_created.message.body.attachments = [
            att_with_bot,
            att_without_bot,
        ]

        _inject_bot(fixture_message_created, bot)

        assert att_with_bot.bot is bot
        # att_without_bot не получает ошибки

    def test_message_body_none_no_error(self, bot, fixture_message_created):
        """Если body=None — нет ошибки."""
        fixture_message_created.message.body = None
        _inject_bot(fixture_message_created, bot)  # не должно падать

    def test_message_none_no_error(self, bot, fixture_message_callback):
        """Если message=None — нет ошибки."""
        fixture_message_callback.message = None
        _inject_bot(fixture_message_callback, bot)  # не должно падать


# ===========================================================================
# enrich_event — сквозной пайплайн
# ===========================================================================


class TestEnrichEvent:
    """Интеграционные тесты для enrich_event."""

    async def test_auto_requests_false_returns_unchanged(
        self, bot, fixture_message_created
    ):
        """auto_requests=False — ранний выход, объект не изменяется."""
        bot.auto_requests = False
        result = await enrich_event(fixture_message_created, bot)
        assert result is fixture_message_created

    async def test_full_pipeline_message_created(
        self, bot, fixture_message_created
    ):
        """Пайплайн: chat, from_user и bot выставляются для MessageCreated."""
        fake_chat = _make_chat(ChatType.DIALOG)
        bot.get_chat_by_id = AsyncMock(return_value=fake_chat)

        result = await enrich_event(fixture_message_created, bot)

        assert result.chat is fake_chat
        assert result.from_user is fixture_message_created.message.sender
        assert result.bot is bot
        assert result.message.bot is bot

    async def test_full_pipeline_bot_removed(self, bot, fixture_bot_removed):
        """BotRemoved: chat=None, from_user=user, bot проставлен."""
        bot.get_chat_by_id = AsyncMock()

        result = await enrich_event(fixture_bot_removed, bot)

        bot.get_chat_by_id.assert_not_called()
        assert result.chat is None
        assert result.from_user is fixture_bot_removed.user
        assert result.bot is bot

    async def test_full_pipeline_dialog_removed(
        self, bot, fixture_dialog_removed
    ):
        """DialogRemoved: chat=None, from_user=user."""
        bot.get_chat_by_id = AsyncMock()

        result = await enrich_event(fixture_dialog_removed, bot)

        bot.get_chat_by_id.assert_not_called()
        assert result.chat is None
        assert result.from_user is fixture_dialog_removed.user

    async def test_full_pipeline_message_removed_chat_type(
        self, bot, fixture_message_removed
    ):
        fake_chat = _make_chat(ChatType.CHAT)
        fake_member = MagicMock()
        bot.get_chat_by_id = AsyncMock(return_value=fake_chat)
        bot.get_chat_member = AsyncMock(return_value=fake_member)

        result = await enrich_event(fixture_message_removed, bot)

        assert result.from_user is fake_member

    async def test_full_pipeline_message_removed_dialog_type(
        self, bot, fixture_message_removed
    ):
        fake_chat = _make_chat(ChatType.DIALOG)
        bot.get_chat_by_id = AsyncMock(return_value=fake_chat)
        bot.get_chat_member = AsyncMock()

        result = await enrich_event(fixture_message_removed, bot)

        bot.get_chat_member.assert_not_called()
        assert result.from_user is fake_chat

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "fixture_user_added",
            "fixture_bot_added",
            "fixture_bot_started",
            "fixture_bot_stopped",
            "fixture_chat_title_changed",
            "fixture_dialog_cleared",
            "fixture_dialog_muted",
            "fixture_dialog_unmuted",
        ],
    )
    async def test_full_pipeline_common_events(
        self, request, bot, fixture_name
    ):
        """Все 'обычные' события: chat загружается, from_user = user."""
        event = request.getfixturevalue(fixture_name)
        fake_chat = _make_chat()
        bot.get_chat_by_id = AsyncMock(return_value=fake_chat)

        result = await enrich_event(event, bot)

        bot.get_chat_by_id.assert_awaited_once_with(event.chat_id)
        assert result.chat is fake_chat
        assert result.from_user is event.user
        assert result.bot is bot
