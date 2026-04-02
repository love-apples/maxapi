"""Тесты retry-механизма для серверных ошибок (502, 503, 504)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientConnectionError
from maxapi import Bot
from maxapi.client.default import (
    DEFAULT_RETRY_STATUSES,
    DefaultConnectionProperties,
)
from maxapi.connection.base import BaseConnection
from maxapi.enums.http_method import HTTPMethod
from maxapi.exceptions.max import (
    InvalidToken,
    MaxApiError,
    MaxConnection,
)


def _make_response(status, *, ok=None, json_data=None):
    """Создаёт мок aiohttp-ответа с async-методами."""
    resp = MagicMock()
    resp.status = status
    resp.ok = ok if ok is not None else (200 <= status < 300)
    resp.read = AsyncMock()
    if json_data is not None:
        resp.json = AsyncMock(return_value=json_data)
    return resp


class TestDefaultConnectionRetryConfig:
    """Тесты конфигурации retry в DefaultConnectionProperties."""

    def test_default_retry_statuses(self):
        """Проверка дефолтных статусов для retry."""
        assert DEFAULT_RETRY_STATUSES == (502, 503, 504)

    def test_default_config(self):
        """Проверка дефолтных параметров retry."""
        conn = DefaultConnectionProperties()
        assert conn.max_retries == 3
        assert conn.retry_on_statuses == (502, 503, 504)
        assert conn.retry_backoff_factor == 1.0

    def test_custom_retry_config(self):
        """Проверка пользовательских параметров retry."""
        conn = DefaultConnectionProperties(
            max_retries=5,
            retry_on_statuses=(502,),
            retry_backoff_factor=0.5,
        )
        assert conn.max_retries == 5
        assert conn.retry_on_statuses == (502,)
        assert conn.retry_backoff_factor == 0.5

    def test_disable_retry(self):
        """Проверка отключения retry."""
        conn = DefaultConnectionProperties(max_retries=0)
        assert conn.max_retries == 0

    def test_negative_max_retries_raises(self):
        """Отрицательный max_retries вызывает ValueError."""
        with pytest.raises(ValueError, match="max_retries"):
            DefaultConnectionProperties(max_retries=-1)


class TestRetryOnServerErrors:
    """Тесты retry при серверных ошибках."""

    @pytest.fixture
    def bot_with_retry(self, mock_bot_token):
        """Бот с настройками retry и мок-сессией."""
        conn = DefaultConnectionProperties(
            max_retries=3,
            retry_on_statuses=(502, 503, 504),
            retry_backoff_factor=0.01,
        )
        bot = Bot(
            token=mock_bot_token,
            default_connection=conn,
        )
        session = AsyncMock()
        bot.session = session
        return bot

    @pytest.mark.asyncio
    async def test_retry_on_502(self, bot_with_retry):
        """Retry при 502 и успех на второй попытке."""
        error = _make_response(502)
        success = _make_response(200, json_data={"success": True})

        bot_with_retry.session.request = AsyncMock(
            side_effect=[error, success]
        )

        base = BaseConnection()
        base.bot = bot_with_retry

        with patch("maxapi.connection.base.asyncio.sleep"):
            result = await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert result == {"success": True}
        assert bot_with_retry.session.request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_503(self, bot_with_retry):
        """Retry при 503 и успех на третьей попытке."""
        error = _make_response(503)
        success = _make_response(200, json_data={"ok": True})

        bot_with_retry.session.request = AsyncMock(
            side_effect=[error, error, success]
        )

        base = BaseConnection()
        base.bot = bot_with_retry

        with patch("maxapi.connection.base.asyncio.sleep"):
            result = await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert result == {"ok": True}
        assert bot_with_retry.session.request.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises_error(self, bot_with_retry):
        """Исчерпание попыток бросает MaxApiError."""
        error = _make_response(502, json_data={"error": "Bad Gateway"})

        bot_with_retry.session.request = AsyncMock(return_value=error)

        base = BaseConnection()
        base.bot = bot_with_retry

        with (
            patch("maxapi.connection.base.asyncio.sleep"),
            pytest.raises(MaxApiError) as exc_info,
        ):
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert exc_info.value.code == 502
        # 1 original + 3 retries = 4 попытки
        assert bot_with_retry.session.request.call_count == 4

    @pytest.mark.asyncio
    async def test_no_retry_on_400(self, bot_with_retry):
        """400 не вызывает retry."""
        error = _make_response(400, json_data={"error": "Bad Request"})

        bot_with_retry.session.request = AsyncMock(return_value=error)

        base = BaseConnection()
        base.bot = bot_with_retry

        with pytest.raises(MaxApiError) as exc_info:
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert exc_info.value.code == 400
        assert bot_with_retry.session.request.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_401(self, bot_with_retry):
        """401 не вызывает retry, бросает InvalidToken."""
        error = _make_response(401)

        bot_with_retry.session.request = AsyncMock(return_value=error)

        base = BaseConnection()
        base.bot = bot_with_retry

        with pytest.raises(InvalidToken):
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert bot_with_retry.session.request.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_disabled(self, mock_bot_token):
        """max_retries=0 отключает retry."""
        conn = DefaultConnectionProperties(
            max_retries=0,
            retry_backoff_factor=0.01,
        )
        bot = Bot(
            token=mock_bot_token,
            default_connection=conn,
        )

        error = _make_response(502, json_data={"error": "Bad Gateway"})

        session = AsyncMock()
        session.request = AsyncMock(return_value=error)
        bot.session = session

        base = BaseConnection()
        base.bot = bot

        with pytest.raises(MaxApiError) as exc_info:
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert exc_info.value.code == 502
        assert session.request.call_count == 1


class TestRetryOnConnectionErrors:
    """Тесты retry при ошибках соединения."""

    @pytest.fixture
    def bot_with_retry(self, mock_bot_token):
        conn = DefaultConnectionProperties(
            max_retries=2,
            retry_backoff_factor=0.01,
        )
        bot = Bot(
            token=mock_bot_token,
            default_connection=conn,
        )
        session = AsyncMock()
        bot.session = session
        return bot

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self, bot_with_retry):
        """Retry при ClientConnectionError."""
        success = _make_response(200, json_data={"ok": True})

        bot_with_retry.session.request = AsyncMock(
            side_effect=[
                ClientConnectionError("Connection refused"),
                success,
            ]
        )

        base = BaseConnection()
        base.bot = bot_with_retry

        with patch("maxapi.connection.base.asyncio.sleep"):
            result = await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert result == {"ok": True}
        assert bot_with_retry.session.request.call_count == 2

    @pytest.mark.asyncio
    async def test_connection_error_exhausted(self, bot_with_retry):
        """Исчерпание попыток при ConnectionError."""
        bot_with_retry.session.request = AsyncMock(
            side_effect=ClientConnectionError("Connection refused")
        )

        base = BaseConnection()
        base.bot = bot_with_retry

        with (
            patch("maxapi.connection.base.asyncio.sleep"),
            pytest.raises(MaxConnection),
        ):
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        # 1 original + 2 retries = 3 попытки
        assert bot_with_retry.session.request.call_count == 3


class TestRetryBackoff:
    """Тесты экспоненциальной задержки."""

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self, mock_bot_token):
        """Проверка экспоненциальных задержек."""
        conn = DefaultConnectionProperties(
            max_retries=3,
            retry_backoff_factor=1.0,
        )
        bot = Bot(
            token=mock_bot_token,
            default_connection=conn,
        )

        error = _make_response(502, json_data={"error": "Bad Gateway"})

        session = AsyncMock()
        session.request = AsyncMock(return_value=error)
        bot.session = session

        base = BaseConnection()
        base.bot = bot

        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with (
            patch(
                "maxapi.connection.base.asyncio.sleep",
                side_effect=mock_sleep,
            ),
            pytest.raises(MaxApiError),
        ):
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        # backoff_factor * 2^attempt: 1*1=1, 1*2=2, 1*4=4
        assert sleep_calls == [1.0, 2.0, 4.0]

    @pytest.mark.asyncio
    async def test_custom_backoff_factor(self, mock_bot_token):
        """Проверка пользовательского backoff_factor."""
        conn = DefaultConnectionProperties(
            max_retries=2,
            retry_backoff_factor=0.5,
        )
        bot = Bot(
            token=mock_bot_token,
            default_connection=conn,
        )

        error = _make_response(503, json_data={"error": "Service Unavailable"})

        session = AsyncMock()
        session.request = AsyncMock(return_value=error)
        bot.session = session

        base = BaseConnection()
        base.bot = bot

        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with (
            patch(
                "maxapi.connection.base.asyncio.sleep",
                side_effect=mock_sleep,
            ),
            pytest.raises(MaxApiError),
        ):
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        # backoff_factor * 2^attempt: 0.5*1=0.5, 0.5*2=1.0
        assert sleep_calls == [0.5, 1.0]


class TestRetryWithCustomStatuses:
    """Тесты retry с пользовательскими статусами."""

    @pytest.mark.asyncio
    async def test_custom_retry_statuses(self, mock_bot_token):
        """Retry с пользовательским набором статусов."""
        conn = DefaultConnectionProperties(
            max_retries=1,
            retry_on_statuses=(429,),
            retry_backoff_factor=0.01,
        )
        bot = Bot(
            token=mock_bot_token,
            default_connection=conn,
        )

        error = _make_response(429)
        success = _make_response(200, json_data={"ok": True})

        session = AsyncMock()
        session.request = AsyncMock(side_effect=[error, success])
        bot.session = session

        base = BaseConnection()
        base.bot = bot

        with patch("maxapi.connection.base.asyncio.sleep"):
            result = await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert result == {"ok": True}
        assert session.request.call_count == 2

    @pytest.mark.asyncio
    async def test_502_not_retried_when_excluded(self, mock_bot_token):
        """502 не ретраится, если убрана из retry_on_statuses."""
        conn = DefaultConnectionProperties(
            max_retries=3,
            retry_on_statuses=(503,),
            retry_backoff_factor=0.01,
        )
        bot = Bot(
            token=mock_bot_token,
            default_connection=conn,
        )

        error = _make_response(502, json_data={"error": "Bad Gateway"})

        session = AsyncMock()
        session.request = AsyncMock(return_value=error)
        bot.session = session

        base = BaseConnection()
        base.bot = bot

        with pytest.raises(MaxApiError) as exc_info:
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert exc_info.value.code == 502
        assert session.request.call_count == 1


class TestRetryResponseBodyConsumed:
    """Тесты корректного освобождения ресурсов при retry."""

    @pytest.mark.asyncio
    async def test_response_body_consumed_on_retry(self, mock_bot_token):
        """Тело ответа читается перед retry для освобождения
        соединения."""
        conn = DefaultConnectionProperties(
            max_retries=1,
            retry_backoff_factor=0.01,
        )
        bot = Bot(
            token=mock_bot_token,
            default_connection=conn,
        )

        error = _make_response(502)
        success = _make_response(200, json_data={"ok": True})

        session = AsyncMock()
        session.request = AsyncMock(side_effect=[error, success])
        bot.session = session

        base = BaseConnection()
        base.bot = bot

        with patch("maxapi.connection.base.asyncio.sleep"):
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        error.read.assert_awaited_once()
