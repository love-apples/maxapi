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
from maxapi.exceptions.max import MaxApiError, MaxConnection
from maxapi.types.fetchable import ChatRef, FromUserRef
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

    async def test_user_removed_api_error_logs_and_keeps_from_user_none(
        self, bot, fixture_user_removed, caplog
    ):
        fixture_user_removed.admin_id = 9999
        bot.get_chat_member = AsyncMock(
            side_effect=MaxApiError(403, "forbidden")
        )

        with caplog.at_level("WARNING", logger="maxapi.utils.updates"):
            await _resolve_from_user(fixture_user_removed, bot)

        assert fixture_user_removed.from_user is None
        assert "Не удалось получить участника чата" in caplog.text

    async def test_user_removed_connection_error_logs_and_keeps_from_user_none(
        self, bot, fixture_user_removed, caplog
    ):
        fixture_user_removed.admin_id = 9999
        bot.get_chat_member = AsyncMock(
            side_effect=MaxConnection("conn error")
        )

        with caplog.at_level("WARNING", logger="maxapi.utils.updates"):
            await _resolve_from_user(fixture_user_removed, bot)

        assert fixture_user_removed.from_user is None
        assert "get_chat_member: conn error" in caplog.text

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

    async def test_auto_requests_false_keeps_object_and_injects_bot(
        self, bot, fixture_message_created
    ):
        """auto_requests=False не делает API-запросов, но bot остаётся."""
        bot.auto_requests = False
        result = await enrich_event(fixture_message_created, bot)
        assert result is fixture_message_created
        assert result.bot is bot
        assert result.message.bot is bot

    async def test_auto_requests_false_message_created_uses_lazy_chat_ref(
        self, bot, fixture_message_created
    ):
        """Chat загружается только по явному вызову fetch()."""
        fake_chat = _make_chat(ChatType.DIALOG)
        bot.auto_requests = False
        bot.get_chat_by_id = AsyncMock(return_value=fake_chat)

        result = await enrich_event(fixture_message_created, bot)

        assert isinstance(result.chat, ChatRef)
        assert result.from_user is fixture_message_created.message.sender
        bot.get_chat_by_id.assert_not_called()

        fetched_chat = await result.chat.fetch()

        assert fetched_chat is fake_chat
        assert result.chat is fake_chat
        bot.get_chat_by_id.assert_awaited_once_with(
            fixture_message_created.message.recipient.chat_id
        )

    async def test_auto_requests_false_message_created_without_chat_id(
        self, bot, fixture_message_created
    ):
        """Без chat_id lazy chat ref не создаётся."""
        fixture_message_created.message.recipient.chat_id = None
        bot.auto_requests = False

        result = await enrich_event(fixture_message_created, bot)

        assert result.chat is None

    async def test_auto_requests_false_message_created_from_user_fetch_is_noop(
        self, bot, fixture_message_created
    ):
        """from_user из payload тоже поддерживает единый fetch API."""
        bot.auto_requests = False

        result = await enrich_event(fixture_message_created, bot)
        fetched_user = await result.from_user.fetch()

        assert fetched_user is fixture_message_created.message.sender

    async def test_auto_requests_false_message_answer_still_works(
        self, bot, fixture_message_created
    ):
        """message.answer не должен ломаться при отключённых auto_requests."""
        bot.auto_requests = False
        bot.send_message = AsyncMock()

        result = await enrich_event(fixture_message_created, bot)
        await result.message.answer(text="hello")

        bot.send_message.assert_awaited_once()

    async def test_auto_requests_false_message_removed_fetches_lazily(
        self,
        bot,
        fixture_message_removed,
    ):
        """MessageRemoved вручную догружает chat и затем участника."""
        fake_chat = _make_chat(ChatType.CHAT)
        fake_member = MagicMock()
        bot.auto_requests = False
        bot.get_chat_by_id = AsyncMock(return_value=fake_chat)
        bot.get_chat_member = AsyncMock(return_value=fake_member)

        result = await enrich_event(fixture_message_removed, bot)

        assert isinstance(result.chat, ChatRef)
        assert isinstance(result.from_user, FromUserRef)
        bot.get_chat_by_id.assert_not_called()
        bot.get_chat_member.assert_not_called()

        fetched_from_user = await result.from_user.fetch()

        assert fetched_from_user is fake_member
        assert result.chat is fake_chat
        assert result.from_user is fake_member
        bot.get_chat_by_id.assert_awaited_once_with(
            fixture_message_removed.chat_id
        )
        bot.get_chat_member.assert_awaited_once_with(
            chat_id=fixture_message_removed.chat_id,
            user_id=fixture_message_removed.user_id,
        )

    async def test_auto_requests_false_user_removed_from_user_fetches_lazily(
        self, bot, fixture_user_removed
    ):
        """UserRemoved с admin_id догружает инициатора только вручную."""
        fake_admin = MagicMock()
        fixture_user_removed.admin_id = 9999
        bot.auto_requests = False
        bot.get_chat_member = AsyncMock(return_value=fake_admin)

        result = await enrich_event(fixture_user_removed, bot)

        assert result.chat is not None
        assert isinstance(result.from_user, FromUserRef)
        bot.get_chat_member.assert_not_called()

        fetched_from_user = await result.from_user.fetch()

        assert fetched_from_user is fake_admin
        assert result.from_user is fake_admin
        bot.get_chat_member.assert_awaited_once_with(
            chat_id=fixture_user_removed.chat_id,
            user_id=fixture_user_removed.admin_id,
        )

    async def test_auto_requests_false_message_removed_dialog_fetch(
        self,
        bot,
        fixture_message_removed,
    ):
        """Lazy fetch должен вернуть chat для DIALOG без get_chat_member."""
        fake_chat = _make_chat(ChatType.DIALOG)
        bot.auto_requests = False
        bot.get_chat_by_id = AsyncMock(return_value=fake_chat)
        bot.get_chat_member = AsyncMock()

        result = await enrich_event(fixture_message_removed, bot)
        fetched_from_user = await result.from_user.fetch()

        assert fetched_from_user is fake_chat
        assert result.from_user is fake_chat
        bot.get_chat_member.assert_not_called()

    async def test_auto_requests_false_message_removed_without_chat(
        self,
        bot,
        fixture_message_removed,
    ):
        """Если chat не найден, lazy fetch from_user тоже возвращает None."""
        bot.auto_requests = False
        bot.get_chat_by_id = AsyncMock(return_value=None)
        bot.get_chat_member = AsyncMock()

        result = await enrich_event(fixture_message_removed, bot)
        fetched_from_user = await result.from_user.fetch()

        assert fetched_from_user is None
        assert result.from_user is None
        bot.get_chat_member.assert_not_called()

    async def test_auto_requests_false_message_removed_unknown_chat_type(
        self, bot, fixture_message_removed
    ):
        """Неизвестный тип чата даёт None вместо from_user."""
        fake_chat = _make_chat()
        fake_chat.type = object()
        bot.auto_requests = False
        bot.get_chat_by_id = AsyncMock(return_value=fake_chat)
        bot.get_chat_member = AsyncMock()

        result = await enrich_event(fixture_message_removed, bot)
        fetched_from_user = await result.from_user.fetch()

        assert fetched_from_user is None
        assert result.from_user is None
        bot.get_chat_member.assert_not_called()

    async def test_auto_requests_false_user_removed_without_admin_keeps_none(
        self, bot, fixture_user_removed
    ):
        """Без admin_id from_user не синтезируется даже как lazy ref."""
        fixture_user_removed.admin_id = None
        bot.auto_requests = False

        result = await enrich_event(fixture_user_removed, bot)

        assert result.from_user is None

    async def test_auto_requests_false_bot_removed_keeps_chat_none(
        self, bot, fixture_bot_removed
    ):
        """BotRemoved не должен получать lazy chat ref."""
        bot.auto_requests = False

        result = await enrich_event(fixture_bot_removed, bot)

        assert result.chat is None
        assert result.from_user is fixture_bot_removed.user

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
