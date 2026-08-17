"""Тесты корректной сборки URL при кастомном api_url с path-префиксом.

При использовании aiohttp.ClientSession(base_url=...) резолюция URL
идёт по RFC 3986 §5.3: путь запроса, начинающийся с "/" (все значения
ApiPath именно такие), считается absolute-path reference и заменяет
весь path базового URL целиком, а не дописывается к нему. Из-за этого
любой path-префикс в кастомном api_url (например, у прокси/шлюза на
нестандартных стендах) молча отбрасывался. См. issue про
set_api_url() с непустым path в базовом URL.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from maxapi import Bot
from maxapi.connection.base import BaseConnection
from maxapi.enums.api_path import ApiPath
from maxapi.enums.http_method import HTTPMethod


def _make_response(status=200, json_data=None):
    """Создаёт мок aiohttp-ответа с async-методами."""
    resp = MagicMock()
    resp.status = status
    resp.ok = 200 <= status < 300
    resp.json = AsyncMock(return_value=json_data or {})
    return resp


class TestRequestUrlWithCustomApiUrl:
    """Тесты сборки итогового URL в BaseConnection.request()."""

    @pytest.fixture
    def bot_with_mock_session(self, mock_bot_token):
        """Бот с мок-сессией, готовой отдать успешный ответ."""
        bot = Bot(token=mock_bot_token)
        session = MagicMock()
        session.closed = False
        session.request = AsyncMock(return_value=_make_response())
        bot.session = session
        return bot

    @pytest.mark.asyncio
    async def test_path_prefix_in_api_url_is_preserved(
        self, bot_with_mock_session
    ):
        """Path-префикс кастомного api_url не отбрасывается."""
        bot_with_mock_session.set_api_url(
            "https://stand.internal/gateway/v1"
        )

        base = BaseConnection()
        base.bot = bot_with_mock_session

        await base.request(
            method=HTTPMethod.GET,
            path=ApiPath.MESSAGES,
            is_return_raw=True,
        )

        called_url = bot_with_mock_session.session.request.call_args.kwargs[
            "url"
        ]
        assert (
            called_url == "https://stand.internal/gateway/v1/messages"
        )

    @pytest.mark.asyncio
    async def test_trailing_slash_in_api_url_does_not_double(
        self, bot_with_mock_session
    ):
        """Trailing slash в api_url не даёт двойной слэш в URL."""
        bot_with_mock_session.set_api_url(
            "https://stand.internal/gateway/v1/"
        )

        base = BaseConnection()
        base.bot = bot_with_mock_session

        await base.request(
            method=HTTPMethod.GET,
            path=ApiPath.ME,
            is_return_raw=True,
        )

        called_url = bot_with_mock_session.session.request.call_args.kwargs[
            "url"
        ]
        assert called_url == "https://stand.internal/gateway/v1/me"

    @pytest.mark.asyncio
    async def test_default_api_url_unchanged(self, bot_with_mock_session):
        """Без кастомного api_url поведение не меняется."""
        base = BaseConnection()
        base.bot = bot_with_mock_session

        await base.request(
            method=HTTPMethod.GET,
            path=ApiPath.CHATS,
            is_return_raw=True,
        )

        called_url = bot_with_mock_session.session.request.call_args.kwargs[
            "url"
        ]
        assert called_url == bot_with_mock_session.api_url + "/chats"


class TestEnsureSessionNoBaseUrl:
    """ClientSession больше не должна создаваться с base_url."""

    @pytest.mark.asyncio
    async def test_ensure_session_omits_base_url(self, mock_bot_token):
        """ensure_session() не передаёт base_url в ClientSession."""
        bot = Bot(token=mock_bot_token)
        bot.set_api_url("https://stand.internal/gateway/v1")
        bot.session = None

        with patch("maxapi.bot.ClientSession") as session_cls:
            session_cls.return_value = MagicMock(closed=False)
            await bot.ensure_session()

        assert "base_url" not in session_cls.call_args.kwargs
