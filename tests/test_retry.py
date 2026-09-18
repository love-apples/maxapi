"""Тесты retry-механизма для временных ошибок (502, 503, 504, 429)."""

import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientConnectionError
from maxapi import Bot
from maxapi.client.default import (
    DEFAULT_RETRY_STATUSES,
    DefaultConnectionProperties,
    RetryEvent,
)
from maxapi.connection.base import (
    RETRY_AFTER_MAX,
    BaseConnection,
    _parse_retry_after,
    _retry_wait,
)
from maxapi.enums.http_method import HTTPMethod
from maxapi.exceptions.download_file import DownloadFileError
from maxapi.exceptions.max import (
    InvalidToken,
    MaxApiError,
    MaxConnection,
)


def _make_response(
    status, *, ok=None, json_data=None, text=None, headers=None
):
    """Создаёт мок aiohttp-ответа с async-методами."""
    resp = MagicMock()
    resp.status = status
    resp.headers = headers or {}
    resp.ok = ok if ok is not None else (200 <= status < 300)
    resp.read = AsyncMock()
    if text is None:
        text = "" if json_data is None else json.dumps(json_data)
    resp.text = AsyncMock(return_value=text)
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
    """Тесты retry при серверных ошибках (через backoff)."""

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
        session = MagicMock()
        session.closed = False
        session.close = AsyncMock()
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

        with patch("asyncio.sleep", new_callable=AsyncMock):
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

        with patch("asyncio.sleep", new_callable=AsyncMock):
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
            patch("asyncio.sleep", new_callable=AsyncMock),
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

        session = MagicMock()
        session.request = AsyncMock(return_value=error)
        session.closed = False
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
        session = MagicMock()
        session.closed = False
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

        with patch("asyncio.sleep", new_callable=AsyncMock):
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
            patch("asyncio.sleep", new_callable=AsyncMock),
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
    """Тесты экспоненциальной задержки через backoff."""

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self, mock_bot_token):
        """Проверка что backoff вызывается нужное количество раз."""
        conn = DefaultConnectionProperties(
            max_retries=3,
            retry_backoff_factor=1.0,
        )
        bot = Bot(
            token=mock_bot_token,
            default_connection=conn,
        )

        error = _make_response(502, json_data={"error": "Bad Gateway"})

        session = MagicMock()
        session.request = AsyncMock(return_value=error)
        session.closed = False
        bot.session = session

        base = BaseConnection()
        base.bot = bot

        sleep_calls = []
        original_sleep = AsyncMock(side_effect=lambda d: sleep_calls.append(d))

        with (
            patch("asyncio.sleep", original_sleep),
            pytest.raises(MaxApiError),
        ):
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        # backoff с экспоненциальной задержкой, 3 retry = 3 sleep
        assert len(sleep_calls) == 3
        assert all(d > 0 for d in sleep_calls)

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

        session = MagicMock()
        session.request = AsyncMock(return_value=error)
        session.closed = False
        bot.session = session

        base = BaseConnection()
        base.bot = bot

        sleep_calls = []
        original_sleep = AsyncMock(side_effect=lambda d: sleep_calls.append(d))

        with (
            patch("asyncio.sleep", original_sleep),
            pytest.raises(MaxApiError),
        ):
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        # 2 retry = 2 sleep
        assert len(sleep_calls) == 2
        assert all(d > 0 for d in sleep_calls)


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

        session = MagicMock()
        session.request = AsyncMock(side_effect=[error, success])
        session.closed = False
        bot.session = session

        base = BaseConnection()
        base.bot = bot

        with patch("asyncio.sleep", new_callable=AsyncMock):
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

        session = MagicMock()
        session.request = AsyncMock(return_value=error)
        session.closed = False
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
        соединения и сохранения в ошибке."""
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

        session = MagicMock()
        session.request = AsyncMock(side_effect=[error, success])
        session.closed = False
        bot.session = session

        base = BaseConnection()
        base.bot = bot

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        error.text.assert_awaited_once()


RATE_LIMIT_STATUSES = (429, *DEFAULT_RETRY_STATUSES)


class TestRateLimitStatus:
    """Тесты обработки 429 (превышение лимита запросов MAX)."""

    @pytest.mark.asyncio
    async def test_429_not_retried_by_default(self, mock_bot_token):
        """С дефолтными настройками 429 сразу поднимает MaxApiError."""
        bot = Bot(token=mock_bot_token)
        session = MagicMock()
        session.closed = False
        session.request = AsyncMock(
            return_value=_make_response(429, text="limit")
        )
        bot.session = session

        base = BaseConnection()
        base.bot = bot

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as sleep,
            pytest.raises(MaxApiError) as exc_info,
        ):
            await base.request(method=HTTPMethod.GET, path="/test")

        assert exc_info.value.code == 429
        assert session.request.call_count == 1
        sleep.assert_not_awaited()

    @pytest.fixture
    def bot_with_defaults(self, mock_bot_token):
        """Бот с явно включённым retry 429 и мок-сессией."""
        conn = DefaultConnectionProperties(
            max_retries=2,
            retry_on_statuses=RATE_LIMIT_STATUSES,
            retry_backoff_factor=0.01,
        )
        bot = Bot(token=mock_bot_token, default_connection=conn)
        session = MagicMock()
        session.closed = False
        session.close = AsyncMock()
        bot.session = session
        return bot

    @pytest.mark.asyncio
    async def test_retry_on_429_when_enabled(self, bot_with_defaults):
        """429 повторяется, если включён в retry_on_statuses."""
        error = _make_response(429)
        success = _make_response(200, json_data={"ok": True})

        bot_with_defaults.session.request = AsyncMock(
            side_effect=[error, success]
        )

        base = BaseConnection()
        base.bot = bot_with_defaults

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert result == {"ok": True}
        assert bot_with_defaults.session.request.call_count == 2

    @pytest.mark.asyncio
    async def test_429_exhausted_raises_max_api_error(self, bot_with_defaults):
        """После исчерпания попыток поднимается MaxApiError с кодом 429."""
        error = _make_response(429, text="rate limit exceeded")
        bot_with_defaults.session.request = AsyncMock(return_value=error)

        base = BaseConnection()
        base.bot = bot_with_defaults

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(MaxApiError) as exc_info,
        ):
            await base.request(method=HTTPMethod.GET, path="/test")

        assert exc_info.value.code == 429
        assert exc_info.value.raw == "rate limit exceeded"


class TestRetryAfterAndHook:
    """Retry-After и пользовательский колбэк on_retry."""

    @staticmethod
    def _bot(mock_bot_token, **conn_kwargs):
        conn = DefaultConnectionProperties(
            max_retries=2, retry_on_statuses=RATE_LIMIT_STATUSES, **conn_kwargs
        )
        bot = Bot(token=mock_bot_token, default_connection=conn)
        session = MagicMock()
        session.closed = False
        session.close = AsyncMock()
        bot.session = session
        base = BaseConnection()
        base.bot = bot
        return bot, base

    def test_wait_is_jittered_expo_without_retry_after(self):
        """Без Retry-After задержка в пределах [0, factor * 2**n]."""
        gen = _retry_wait(1.0)
        next(gen)
        for bound in (1, 2, 4):
            assert 0 <= gen.send(Exception()) <= bound

    @pytest.mark.asyncio
    async def test_retry_after_header_is_respected(self, mock_bot_token):
        """Задержка берётся из Retry-After, а не из backoff."""
        bot, base = self._bot(mock_bot_token)
        error = _make_response(429, headers={"Retry-After": "7"})
        success = _make_response(200, json_data={"ok": True})
        bot.session.request = AsyncMock(side_effect=[error, success])

        with patch("asyncio.sleep", new_callable=AsyncMock) as sleep:
            await base.request(
                method=HTTPMethod.GET, path="/test", is_return_raw=True
            )

        sleep.assert_awaited_once_with(7.0)

    @pytest.mark.asyncio
    async def test_on_retry_receives_event(self, mock_bot_token):
        """Асинхронный колбэк получает статус, попытку, задержку и тело."""
        events: list[RetryEvent] = []

        async def on_retry(event: RetryEvent) -> None:
            events.append(event)

        bot, base = self._bot(mock_bot_token, on_retry=on_retry)
        error = _make_response(
            429, text="slow down", headers={"Retry-After": "3"}
        )
        success = _make_response(200, json_data={"ok": True})
        bot.session.request = AsyncMock(side_effect=[error, success])

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await base.request(
                method=HTTPMethod.GET, path="/test", is_return_raw=True
            )

        assert events == [
            RetryEvent(status=429, attempt=1, delay=3.0, body="slow down")
        ]

    @pytest.mark.asyncio
    async def test_on_retry_false_cancels_retry(self, mock_bot_token):
        """Колбэк, вернувший False, сразу отдаёт MaxApiError без повтора."""
        bot, base = self._bot(mock_bot_token, on_retry=lambda event: False)
        bot.session.request = AsyncMock(
            return_value=_make_response(429, text="limit")
        )

        with (
            patch("asyncio.sleep", new_callable=AsyncMock) as sleep,
            pytest.raises(MaxApiError) as exc_info,
        ):
            await base.request(method=HTTPMethod.GET, path="/test")

        assert exc_info.value.code == 429
        assert bot.session.request.call_count == 1
        sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_huge_retry_after_is_capped(self, mock_bot_token):
        """Огромный Retry-After не замораживает request()."""
        bot, base = self._bot(mock_bot_token)
        error = _make_response(429, headers={"Retry-After": "999999999"})
        success = _make_response(200, json_data={"ok": True})
        bot.session.request = AsyncMock(side_effect=[error, success])

        with patch("asyncio.sleep", new_callable=AsyncMock) as sleep:
            await base.request(
                method=HTTPMethod.GET, path="/test", is_return_raw=True
            )

        sleep.assert_awaited_once_with(RETRY_AFTER_MAX)

    @pytest.mark.asyncio
    async def test_on_retry_exception_propagates(self, mock_bot_token):
        """Исключение из on_retry уходит из request() как есть."""

        class StopRetry(Exception):
            pass

        def on_retry(event: RetryEvent) -> None:
            raise StopRetry

        bot, base = self._bot(mock_bot_token, on_retry=on_retry)
        bot.session.request = AsyncMock(return_value=_make_response(429))

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(StopRetry),
        ):
            await base.request(method=HTTPMethod.GET, path="/test")

        assert bot.session.request.call_count == 1

    @pytest.mark.asyncio
    async def test_fetch_response_respects_retry_after(self, mock_bot_token):
        """_fetch_response учитывает Retry-After и вызывает on_retry."""
        events: list[RetryEvent] = []
        bot, base = self._bot(mock_bot_token, on_retry=events.append)
        error = _make_response(503, headers={"Retry-After": "2"})
        success = _make_response(200)
        bot.session.request = AsyncMock(side_effect=[error, success])

        with patch("asyncio.sleep", new_callable=AsyncMock) as sleep:
            response = await base._fetch_response("https://example.com/f")

        assert response is success
        sleep.assert_awaited_once_with(2.0)
        assert [(e.status, e.delay) for e in events] == [(503, 2.0)]

    @pytest.mark.asyncio
    async def test_fetch_response_on_retry_false(self, mock_bot_token):
        """Отмена повтора в _fetch_response даёт DownloadFileError."""
        bot, base = self._bot(mock_bot_token, on_retry=lambda event: False)
        bot.session.request = AsyncMock(return_value=_make_response(429))

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(DownloadFileError, match="429"),
        ):
            await base._fetch_response("https://example.com/f")

        assert bot.session.request.call_count == 1


class TestParseRetryAfter:
    """Разбор заголовка Retry-After."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("0", 0.0),
            ("5", 5.0),
            (" 7 ", 7.0),
            ("1.5", 1.5),
            ("999999999", RETRY_AFTER_MAX),
            ("1" * 400, RETRY_AFTER_MAX),
        ],
    )
    def test_seconds(self, value, expected):
        """Число секунд принимается и ограничивается потолком."""
        assert _parse_retry_after(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            None,
            "",
            "   ",
            "-5",
            "inf",
            "Infinity",
            "nan",
            "1e9",
            "+5",
            "abc",
            "5s",
            "\u0665",  # арабско-индийская цифра 5
            "Mon, 99 Foo 2026 25:61:61 GMT",
        ],
    )
    def test_invalid_values_are_ignored(self, value):
        """Мусор, отрицательные и нечисловые значения отбрасываются."""
        assert _parse_retry_after(value) is None

    def test_http_date_in_future(self):
        """HTTP-дата превращается в задержку до неё."""
        when = datetime.now(timezone.utc) + timedelta(seconds=30)
        delay = _parse_retry_after(format_datetime(when, usegmt=True))
        assert delay is not None
        assert 28 <= delay <= 30

    def test_http_date_in_past_is_zero(self):
        """HTTP-дата в прошлом даёт нулевую задержку."""
        when = datetime.now(timezone.utc) - timedelta(hours=1)
        assert _parse_retry_after(format_datetime(when, usegmt=True)) == 0.0

    def test_far_future_http_date_is_capped(self):
        """Дата в далёком будущем ограничивается потолком."""
        when = datetime.now(timezone.utc) + timedelta(days=365)
        assert (
            _parse_retry_after(format_datetime(when, usegmt=True))
            == RETRY_AFTER_MAX
        )
