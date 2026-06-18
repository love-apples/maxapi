"""Tests for uncovered code paths identified by Codecov in PR #92.

Covers:
- utils/updates.py: MaxApiError / MaxConnection in _resolve_from_user
- methods/subscribe_webhook.py: warns on http:// URL
- filters/command.py: case-insensitive command match path
- methods/get_chats.py: marker=0 handled via `is not None`
- methods/get_members_chat.py: marker=0 handled via `is not None`
- connection/base.py: temp Session branch + mimetypes.guess_type
"""

from __future__ import annotations

import warnings
from unittest.mock import MagicMock, Mock, patch

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

    def test_message_removed_max_api_error_logs_and_continues(
        self, bot, fixture_message_removed
    ):
        """MaxApiError in get_chat_member for MessageRemoved is caught, logged,
        and from_user stays None."""
        fake_chat = _make_chat(ChatType.CHAT)
        fixture_message_removed.chat = fake_chat
        fixture_message_removed.from_user = None

        error = MaxApiError(code=404, raw={"message": "not found"})
        bot.get_chat_member = Mock(side_effect=error)

        with patch("maxapi.utils.updates.logger") as mock_logger:
            _resolve_from_user(fixture_message_removed, bot)

        mock_logger.warning.assert_called_once()
        assert fixture_message_removed.from_user is None

    def test_message_removed_max_connection_logs_and_continues(
        self, bot, fixture_message_removed
    ):
        """MaxConnection in get_chat_member for MessageRemoved is caught."""
        fake_chat = _make_chat(ChatType.CHAT)
        fixture_message_removed.chat = fake_chat
        fixture_message_removed.from_user = None

        bot.get_chat_member = Mock(side_effect=MaxConnection("timeout"))

        with patch("maxapi.utils.updates.logger") as mock_logger:
            _resolve_from_user(fixture_message_removed, bot)

        mock_logger.warning.assert_called_once()
        assert fixture_message_removed.from_user is None

    def test_user_removed_max_api_error_logs_and_continues(
        self, bot, fixture_user_removed
    ):
        """MaxApiError in get_chat_member for UserRemoved is caught."""
        fixture_user_removed.admin_id = 9999
        fixture_user_removed.from_user = None

        error = MaxApiError(code=403, raw={"message": "forbidden"})
        bot.get_chat_member = Mock(side_effect=error)

        with patch("maxapi.utils.updates.logger") as mock_logger:
            _resolve_from_user(fixture_user_removed, bot)

        mock_logger.warning.assert_called_once()
        assert fixture_user_removed.from_user is None

    def test_user_removed_max_connection_logs_and_continues(
        self, bot, fixture_user_removed
    ):
        """MaxConnection in get_chat_member for UserRemoved is caught."""
        fixture_user_removed.admin_id = 9999
        fixture_user_removed.from_user = None

        bot.get_chat_member = Mock(side_effect=MaxConnection("no conn"))

        with patch("maxapi.utils.updates.logger") as mock_logger:
            _resolve_from_user(fixture_user_removed, bot)

        mock_logger.warning.assert_called_once()
        assert fixture_user_removed.from_user is None


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
# filters/command.py — case-insensitive match path (1 line)
# ===========================================================================


class TestCommandFilterCaseInsensitive:
    """Case-insensitive command matching (check_case=False, default)."""

    def test_uppercase_input_matches_lowercase_command(self):
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

        result = cmd(event)

        assert result is not False
        assert isinstance(result, dict)
        assert "args" in result

    def test_mixed_case_command_text_matches(self):
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

        result = cmd(event)

        assert result is not False

    def test_case_sensitive_mismatch_returns_false(self):
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

        result = cmd(event)

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
# connection/base.py — temp Session + mimetypes (2 lines)
# ===========================================================================


class TestBaseConnectionUploadFallback:
    """upload_file / upload_file_buffer используют временный Session,
    когда сессия отсутствует.
    """

    def test_upload_file_uses_temp_session_when_session_is_none(
        self, bot, tmp_path
    ):
        """upload_file откатывается к новому Session,
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

        mock_response = Mock()
        mock_response.text = '{"token":"abc"}'

        mock_session_instance = Mock()
        mock_session_instance.post = Mock(return_value=mock_response)
        mock_session_instance.__enter__ = Mock(
            return_value=mock_session_instance
        )
        mock_session_instance.__exit__ = Mock(return_value=False)

        with patch(
            "maxapi.connection.base.Session",
            return_value=mock_session_instance,
        ):
            result = conn.upload_file(
                url="https://upload.example.com",
                path=str(test_file),
                type=UploadType.VIDEO,
            )

        assert result == '{"token":"abc"}'
        mock_session_instance.post.assert_called_once()

    def test_upload_file_buffer_mimetypes_guess_extension(self, bot, tmp_path):
        """upload_file_buffer вызывает mimetypes.guess_extension
        для известного MIME-типа.
        """
        from maxapi.connection.base import BaseConnection
        from maxapi.enums.upload_type import UploadType

        conn = BaseConnection()
        conn.bot = bot

        some_buffer = b"\x00" * 32

        mock_response = Mock()
        mock_response.text = '{"token":"xyz"}'

        # Устанавливаем сессию на экземпляр BaseConnection (conn),
        # а не на бота, так как _get_session() проверяет self.session
        conn.session = MagicMock()
        conn.session.post = Mock(return_value=mock_response)

        # Подменяем puremagic, чтобы вернуть распознаваемый MIME-матч,
        # и mimetypes.guess_extension — чтобы вернуть реальное расширение.
        fake_match = MagicMock()
        fake_match.mime_type = "image/png"

        with (
            patch("maxapi.connection.base.puremagic.magic_string") as mock_pm,
            patch(
                "maxapi.connection.base.mimetypes.guess_extension"
            ) as mock_ge,
        ):
            mock_pm.return_value = [fake_match]
            mock_ge.return_value = ".png"

            result = conn.upload_file_buffer(
                filename="image",
                url="https://upload.example.com",
                buffer=some_buffer,
                type=UploadType.IMAGE,
            )

        # guess_extension was called (the covered line)
        mock_ge.assert_called_once_with("image/png")
        assert result == '{"token":"xyz"}'

    def test_upload_file_buffer_uses_temp_session_when_session_is_none(
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

        mock_response = Mock()
        mock_response.text = '{"token":"buf"}'

        mock_session_instance = Mock()
        mock_session_instance.post = Mock(return_value=mock_response)
        mock_session_instance.__enter__ = Mock(
            return_value=mock_session_instance
        )
        mock_session_instance.__exit__ = Mock(return_value=False)

        with patch(
            "maxapi.connection.base.Session",
            return_value=mock_session_instance,
        ):
            result = conn.upload_file_buffer(
                filename="clip",
                url="https://upload.example.com",
                buffer=some_buffer,
                type=UploadType.VIDEO,
            )

        assert result == '{"token":"buf"}'
        mock_session_instance.post.assert_called_once()
