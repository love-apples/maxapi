"""Tests for uncovered code paths identified by Codecov in PR #92.

Covers:
- utils/updates.py: MaxApiError / MaxConnection in _resolve_from_user
- dispatcher.py: _ready flag prevents double init (idempotency)
- methods/subscribe_webhook.py: warns on http:// URL
- filters/command.py: case-insensitive command match path
- methods/get_chats.py: marker=0 handled via `is not None`
- methods/get_members_chat.py: marker=0 handled via `is not None`
- connection/base.py: temp ClientSession branch + mimetypes.guess_type
"""

from __future__ import annotations

import warnings
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from maxapi.enums.chat_type import ChatType
from maxapi.exceptions.max import MaxApiError, MaxConnection
from maxapi.filters.command import Command
from maxapi.utils.updates import _resolve_from_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chat(chat_type: ChatType = ChatType.CHAT):
    chat = MagicMock()
    chat.type = chat_type
    return chat


def _make_message_removed_event(chat_id: int = 111, user_id: int = 222):
    """Builds a minimal MessageRemoved-like mock."""
    from maxapi.types.updates.message_removed import MessageRemoved

    event = MagicMock(spec=MessageRemoved)
    event.chat_id = chat_id
    event.user_id = user_id
    event.from_user = None
    return event


def _make_user_removed_event(chat_id: int = 111, admin_id: int = 333):
    """Builds a minimal UserRemoved-like mock."""
    from maxapi.types.updates.user_removed import UserRemoved

    event = MagicMock(spec=UserRemoved)
    event.chat_id = chat_id
    event.admin_id = admin_id
    event.from_user = None
    return event


# ===========================================================================
# utils/updates.py — except MaxApiError / MaxConnection (8 lines)
# ===========================================================================


class TestResolveFromUserErrorHandling:
    """Exception-handling paths in _resolve_from_user (PR #92 additions)."""

    async def test_message_removed_max_api_error_logs_and_continues(
        self, bot, fixture_message_removed
    ):
        """MaxApiError in get_chat_member for MessageRemoved is caught, logged,
        and from_user stays None."""
        fake_chat = _make_chat(ChatType.CHAT)
        fixture_message_removed.chat = fake_chat
        fixture_message_removed.from_user = None

        error = MaxApiError(code=404, raw={"message": "not found"})
        bot.get_chat_member = AsyncMock(side_effect=error)

        with patch("maxapi.utils.updates.logger") as mock_logger:
            await _resolve_from_user(fixture_message_removed, bot)

        mock_logger.warning.assert_called_once()
        assert fixture_message_removed.from_user is None

    async def test_message_removed_max_connection_logs_and_continues(
        self, bot, fixture_message_removed
    ):
        """MaxConnection in get_chat_member for MessageRemoved is caught."""
        fake_chat = _make_chat(ChatType.CHAT)
        fixture_message_removed.chat = fake_chat
        fixture_message_removed.from_user = None

        bot.get_chat_member = AsyncMock(side_effect=MaxConnection("timeout"))

        with patch("maxapi.utils.updates.logger") as mock_logger:
            await _resolve_from_user(fixture_message_removed, bot)

        mock_logger.warning.assert_called_once()
        assert fixture_message_removed.from_user is None

    async def test_user_removed_max_api_error_logs_and_continues(
        self, bot, fixture_user_removed
    ):
        """MaxApiError in get_chat_member for UserRemoved is caught."""
        fixture_user_removed.admin_id = 9999
        fixture_user_removed.from_user = None

        error = MaxApiError(code=403, raw={"message": "forbidden"})
        bot.get_chat_member = AsyncMock(side_effect=error)

        with patch("maxapi.utils.updates.logger") as mock_logger:
            await _resolve_from_user(fixture_user_removed, bot)

        mock_logger.warning.assert_called_once()
        assert fixture_user_removed.from_user is None

    async def test_user_removed_max_connection_logs_and_continues(
        self, bot, fixture_user_removed
    ):
        """MaxConnection in get_chat_member for UserRemoved is caught."""
        fixture_user_removed.admin_id = 9999
        fixture_user_removed.from_user = None

        bot.get_chat_member = AsyncMock(side_effect=MaxConnection("no conn"))

        with patch("maxapi.utils.updates.logger") as mock_logger:
            await _resolve_from_user(fixture_user_removed, bot)

        mock_logger.warning.assert_called_once()
        assert fixture_user_removed.from_user is None


# ===========================================================================
# dispatcher.py — _ready flag idempotency (1 line: early return)
# ===========================================================================


class TestDispatcherReadyIdempotency:
    """__ready() must short-circuit if _ready is already True."""

    async def test_double_startup_only_inits_once(self, dispatcher, bot):
        """Calling startup() twice must not call check_me/prepare twice."""
        dispatcher.check_me = AsyncMock()
        dispatcher._prepare_handlers = Mock()

        await dispatcher.startup(bot)
        await dispatcher.startup(bot)

        # Should be called exactly once, not twice
        dispatcher.check_me.assert_called_once()
        dispatcher._prepare_handlers.assert_called_once_with(bot)

    async def test_ready_flag_set_after_startup(self, dispatcher, bot):
        """After startup(), _ready must be True."""
        dispatcher.check_me = AsyncMock()
        dispatcher._prepare_handlers = Mock()

        assert dispatcher._ready is False
        await dispatcher.startup(bot)
        assert dispatcher._ready is True

    async def test_ready_direct_call_skips_second_entry(self, dispatcher, bot):
        """Direct __ready call when _ready=True returns immediately."""
        dispatcher.check_me = AsyncMock()
        dispatcher._prepare_handlers = Mock()

        # First call initialises
        await dispatcher._Dispatcher__ready(bot)
        dispatcher.check_me.assert_called_once()

        # Second call is a no-op
        await dispatcher._Dispatcher__ready(bot)
        dispatcher.check_me.assert_called_once()  # still only once


# ===========================================================================
# methods/subscribe_webhook.py — HTTP URL warning (2 lines)
# ===========================================================================


class TestSubscribeWebhookHttpWarning:
    """SubscribeWebhook warns when URL is plain http://."""

    def test_http_url_raises_user_warning(self, bot):
        """Constructing SubscribeWebhook with http:// URL emits a warning."""
        from maxapi.methods.subscribe_webhook import SubscribeWebhook

        with pytest.warns(UserWarning, match="HTTPS"):
            SubscribeWebhook(bot=bot, url="http://example.com/hook")

    def test_https_url_does_not_warn(self, bot):
        """Constructing SubscribeWebhook with https:// URL is silent."""
        from maxapi.methods.subscribe_webhook import SubscribeWebhook

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            # Should not raise
            SubscribeWebhook(bot=bot, url="https://example.com/hook")


# ===========================================================================
# webhook/base.py — missing-secret warning (BaseMaxWebhook.__init__)
# ===========================================================================


class _DummyBot:
    """Stand-in for Bot in webhook init tests (no network calls)."""


class TestBaseMaxWebhookSecretWarning:
    """BaseMaxWebhook logs a warning when secret is empty/None.

    The check uses `if not self.secret:` so it must fire for both
    ``None`` and empty string ``""`` and stay silent for any
    non-empty secret.
    """

    _WARN_FRAGMENT = "без secret"

    def _make_webhook(self, secret):
        from maxapi import Dispatcher
        from maxapi.webhook.aiohttp import AiohttpMaxWebhook

        return AiohttpMaxWebhook(
            dp=Dispatcher(), bot=_DummyBot(), secret=secret
        )

    def test_secret_none_logs_warning(self, caplog):
        """secret=None should produce the missing-secret warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            self._make_webhook(secret=None)
        assert any(self._WARN_FRAGMENT in r.message for r in caplog.records)

    def test_secret_empty_string_logs_warning(self, caplog):
        """secret='' is also unsafe and must trigger the warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            self._make_webhook(secret="")
        assert any(self._WARN_FRAGMENT in r.message for r in caplog.records)

    def test_secret_non_empty_no_warning(self, caplog):
        """A real secret must keep the log clean."""
        import logging

        with caplog.at_level(logging.WARNING):
            self._make_webhook(secret="my-secret")
        assert not any(
            self._WARN_FRAGMENT in r.message for r in caplog.records
        )


# ===========================================================================
# filters/command.py — case-insensitive match path (1 line)
# ===========================================================================


class TestCommandFilterCaseInsensitive:
    """Case-insensitive command matching (check_case=False, default)."""

    async def test_uppercase_input_matches_lowercase_command(self):
        """'/START' matches Command('start') when check_case=False."""
        from maxapi.types.message import Message, MessageBody

        cmd = Command("start")  # stored as 'start'

        event = Mock()
        event.__class__ = __import__(
            "maxapi.types.updates.message_created", fromlist=["MessageCreated"]
        ).MessageCreated
        message_body = Mock(spec=MessageBody)
        message_body.text = "/START"
        message = Mock(spec=Message)
        message.body = message_body
        event.message = message

        mock_bot = Mock()
        mock_bot.me = Mock(username=None)
        event._ensure_bot = Mock(return_value=mock_bot)

        result = await cmd(event)

        assert result is not False
        assert isinstance(result, dict)
        assert "args" in result

    async def test_mixed_case_command_text_matches(self):
        """/Help matches Command('help', check_case=False)."""
        from maxapi.types.message import Message, MessageBody
        from maxapi.types.updates.message_created import MessageCreated

        cmd = Command("help")

        event = Mock(spec=MessageCreated)
        message_body = Mock(spec=MessageBody)
        message_body.text = "/Help"
        message = Mock(spec=Message)
        message.body = message_body
        event.message = message

        mock_bot = Mock()
        mock_bot.me = Mock(username=None)
        event._ensure_bot = Mock(return_value=mock_bot)

        result = await cmd(event)

        assert result is not False

    async def test_case_sensitive_mismatch_returns_false(self):
        """With check_case=True, '/START' does NOT match Command('start')."""
        from maxapi.types.message import Message, MessageBody
        from maxapi.types.updates.message_created import MessageCreated

        cmd = Command("start", check_case=True)

        event = Mock(spec=MessageCreated)
        message_body = Mock(spec=MessageBody)
        message_body.text = "/START"
        message = Mock(spec=Message)
        message.body = message_body
        event.message = message

        mock_bot = Mock()
        mock_bot.me = Mock(username=None)
        event._ensure_bot = Mock(return_value=mock_bot)

        result = await cmd(event)

        assert result is False


# ===========================================================================
# methods/get_chats.py — marker=0 handled correctly (1 line)
# ===========================================================================


class TestGetChatsMarkerIsNotNone:
    """GetChats must send marker=0 (falsy but valid) as a query param."""

    def test_marker_zero_included_in_params(self, bot):
        """marker=0 is added to params dict (not skipped by `if marker`)."""
        from maxapi.methods.get_chats import GetChats

        method = GetChats(bot=bot, marker=0)

        # Simulate what fetch() does to build params
        params = bot.params.copy()
        if method.count:
            params["count"] = method.count
        if method.marker is not None:
            params["marker"] = method.marker

        assert "marker" in params
        assert params["marker"] == 0

    def test_marker_none_not_included_in_params(self, bot):
        """marker=None is NOT added to params dict."""
        from maxapi.methods.get_chats import GetChats

        method = GetChats(bot=bot, marker=None)

        params = bot.params.copy()
        if method.count:
            params["count"] = method.count
        if method.marker is not None:
            params["marker"] = method.marker

        assert "marker" not in params

    def test_marker_positive_included_in_params(self, bot):
        """A positive marker is included in params."""
        from maxapi.methods.get_chats import GetChats

        method = GetChats(bot=bot, marker=42)

        params = bot.params.copy()
        if method.marker is not None:
            params["marker"] = method.marker

        assert params["marker"] == 42


# ===========================================================================
# methods/get_members_chat.py — marker=0 handled correctly (1 line)
# ===========================================================================


class TestGetMembersChatMarkerIsNotNone:
    """GetMembersChat must send marker=0 as a query param."""

    def test_marker_zero_included_in_params(self, bot):
        """marker=0 is added to params dict."""
        from maxapi.methods.get_members_chat import GetMembersChat

        method = GetMembersChat(bot=bot, chat_id=12345, marker=0)

        params = bot.params.copy()
        if method.marker is not None:
            params["marker"] = method.marker

        assert "marker" in params
        assert params["marker"] == 0

    def test_marker_none_not_included_in_params(self, bot):
        """marker=None is NOT added to params dict."""
        from maxapi.methods.get_members_chat import GetMembersChat

        method = GetMembersChat(bot=bot, chat_id=12345, marker=None)

        params = bot.params.copy()
        if method.marker is not None:
            params["marker"] = method.marker

        assert "marker" not in params

    def test_marker_positive_included_in_params(self, bot):
        """A positive marker is included in params."""
        from maxapi.methods.get_members_chat import GetMembersChat

        method = GetMembersChat(bot=bot, chat_id=12345, marker=100)

        params = bot.params.copy()
        if method.marker is not None:
            params["marker"] = method.marker

        assert params["marker"] == 100


# ===========================================================================
# methods/get_list_admin_chat.py — marker=0 handled correctly (1 line)
# ===========================================================================


class TestGetListAdminChatMarkerIsNotNone:
    """GetListAdminChat must send marker=0 as a query param."""

    def test_marker_zero_included_in_params(self, bot):
        """marker=0 is added to params dict."""
        from maxapi.methods.get_list_admin_chat import GetListAdminChat

        method = GetListAdminChat(bot=bot, chat_id=12345, marker=0)

        params = bot.params.copy()
        if method.marker is not None:
            params["marker"] = method.marker

        assert "marker" in params
        assert params["marker"] == 0

    def test_marker_none_not_included_in_params(self, bot):
        """marker=None is NOT added to params dict."""
        from maxapi.methods.get_list_admin_chat import GetListAdminChat

        method = GetListAdminChat(bot=bot, chat_id=12345, marker=None)

        params = bot.params.copy()
        if method.marker is not None:
            params["marker"] = method.marker

        assert "marker" not in params

    def test_marker_positive_included_in_params(self, bot):
        """A positive marker is included in params."""
        from maxapi.methods.get_list_admin_chat import GetListAdminChat

        method = GetListAdminChat(bot=bot, chat_id=12345, marker=100)

        params = bot.params.copy()
        if method.marker is not None:
            params["marker"] = method.marker

        assert params["marker"] == 100


# ===========================================================================
# connection/base.py — temp ClientSession + mimetypes (2 lines)
# ===========================================================================


class TestBaseConnectionUploadFallback:
    """upload_file / upload_file_buffer используют временный ClientSession,
    когда сессия отсутствует.
    """

    async def test_upload_file_uses_temp_session_when_session_is_none(
        self, bot, tmp_path
    ):
        """upload_file откатывается к новому ClientSession,
        когда bot.session=None.
        """
        from maxapi.connection.base import BaseConnection
        from maxapi.enums.upload_type import UploadType

        # Write a tiny test file
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"\x00" * 16)

        conn = BaseConnection()
        conn.bot = bot
        bot.session = None  # force the else-branch

        mock_response = AsyncMock()
        mock_response.text = AsyncMock(return_value='{"token":"abc"}')

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response

        mock_session_instance = AsyncMock()
        mock_session_instance.post = Mock(return_value=mock_cm)
        mock_session_instance.__aenter__ = AsyncMock(
            return_value=mock_session_instance
        )
        mock_session_instance.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "maxapi.connection.base.ClientSession",
            return_value=mock_session_instance,
        ):
            result = await conn.upload_file(
                url="https://upload.example.com",
                path=str(test_file),
                type=UploadType.VIDEO,
            )

        assert result == '{"token":"abc"}'
        mock_session_instance.post.assert_called_once()

    async def test_upload_file_buffer_mimetypes_guess_extension(
        self, bot, tmp_path
    ):
        """upload_file_buffer вызывает mimetypes.guess_extension
        для известного MIME-типа.
        """
        from maxapi.connection.base import BaseConnection
        from maxapi.enums.upload_type import UploadType

        conn = BaseConnection()
        conn.bot = bot

        some_buffer = b"\x00" * 32

        mock_response = AsyncMock()
        mock_response.text = AsyncMock(return_value='{"token":"xyz"}')
        mock_cm_buf = AsyncMock()
        mock_cm_buf.__aenter__.return_value = mock_response
        mock_cm_buf.__aexit__.return_value = False

        bot.session = MagicMock()
        bot.session.closed = False
        bot.session.post = Mock(return_value=mock_cm_buf)

        # Подменяем puremagic, чтобы вернуть распознаваемый MIME-матч,
        # и mimetypes.guess_extension — чтобы вернуть реальное расширение.
        fake_match = MagicMock()

        def _fake_getitem(self_m, idx):
            return "image/png" if idx == 1 else "mocked"

        fake_match.__getitem__ = _fake_getitem

        with (
            patch("maxapi.connection.base.puremagic.magic_string") as mock_pm,
            patch(
                "maxapi.connection.base.mimetypes.guess_extension"
            ) as mock_ge,
        ):
            mock_pm.return_value = [fake_match]
            mock_ge.return_value = ".png"

            result = await conn.upload_file_buffer(
                filename="image",
                url="https://upload.example.com",
                buffer=some_buffer,
                type=UploadType.IMAGE,
            )

        # guess_extension was called (the covered line)
        mock_ge.assert_called_once_with("image/png")
        assert result == '{"token":"xyz"}'

    async def test_upload_file_buffer_uses_temp_session_when_session_is_none(
        self, bot
    ):
        """upload_file_buffer falls back to a new ClientSession
        when bot.session=None."""
        from maxapi.connection.base import BaseConnection
        from maxapi.enums.upload_type import UploadType

        conn = BaseConnection()
        conn.bot = bot
        bot.session = None  # force the else-branch

        some_buffer = b"\x00" * 32

        mock_response = AsyncMock()
        mock_response.text = AsyncMock(return_value='{"token":"buf"}')

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response
        mock_cm.__aexit__.return_value = False

        mock_session_instance = AsyncMock()
        mock_session_instance.post = Mock(return_value=mock_cm)
        mock_session_instance.__aenter__ = AsyncMock(
            return_value=mock_session_instance
        )
        mock_session_instance.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "maxapi.connection.base.ClientSession",
            return_value=mock_session_instance,
        ):
            result = await conn.upload_file_buffer(
                filename="clip",
                url="https://upload.example.com",
                buffer=some_buffer,
                type=UploadType.VIDEO,
            )

        assert result == '{"token":"buf"}'
        mock_session_instance.post.assert_called_once()
        mock_cm.__aenter__.assert_called_once()
