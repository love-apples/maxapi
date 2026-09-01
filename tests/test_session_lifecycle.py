"""Тесты жизненного цикла HTTP-сессии и её коннектора.

Регрессия на issue #197: пользовательский коннектор не должен
закрываться сессиями бота, а ответ 401 — рвать разделяемую сессию
из-под параллельных запросов.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientSession, TCPConnector
from maxapi import Bot
from maxapi.client.default import DefaultConnectionProperties
from maxapi.connection.base import BaseConnection
from maxapi.enums.http_method import HTTPMethod
from maxapi.enums.update import UpdateType
from maxapi.enums.upload_type import UploadType
from maxapi.exceptions.download_file import DownloadFileError
from maxapi.exceptions.max import InvalidToken, MaxConnection


def _make_401(*, json_data=None, text=None):
    """Мок ответа 401 с настраиваемым телом."""
    resp = MagicMock()
    resp.status = 401
    resp.ok = False
    resp.release = MagicMock()
    if json_data is not None:
        resp.json = AsyncMock(return_value=json_data)
    else:
        resp.json = AsyncMock(side_effect=ValueError("not json"))
    resp.text = AsyncMock(return_value=text if text is not None else "")
    return resp


async def _drain_tasks() -> None:
    """Отдаёт управление циклу, чтобы отработали созданные задачи."""
    await asyncio.sleep(0)


class TestCustomConnectorOwnership:
    """Пользовательский коннектор переживает закрытие сессий."""

    async def test_close_session_keeps_custom_connector_alive(
        self, mock_bot_token
    ):
        """close_session() не закрывает чужой коннектор."""
        connector = TCPConnector()
        bot = Bot(
            token=mock_bot_token,
            default_connection=DefaultConnectionProperties(
                connector=connector
            ),
        )

        try:
            first = await bot.ensure_session()
            await bot.close_session()

            assert first.closed is True
            assert connector.closed is False

            second = await bot.ensure_session()

            assert second is not first
            assert second.closed is False

            await bot.close_session()
            assert connector.closed is False
        finally:
            await connector.close()

    async def test_temp_upload_session_keeps_custom_connector_alive(
        self, mock_bot_token, tmp_path
    ):
        """Временная сессия upload_file не закрывает чужой коннектор."""
        connector = TCPConnector()
        bot = Bot(
            token=mock_bot_token,
            default_connection=DefaultConnectionProperties(
                connector=connector
            ),
        )
        bot.session = None

        conn = BaseConnection()
        conn.bot = bot

        test_file = tmp_path / "photo.png"
        test_file.write_bytes(b"fake-png-data")

        created: list[ClientSession] = []
        original_post = ClientSession.post

        def fake_post(self, *args, **kwargs):
            created.append(self)
            response = AsyncMock()
            response.text = AsyncMock(return_value="ok")
            cm = AsyncMock()
            cm.__aenter__.return_value = response
            cm.__aexit__.return_value = False
            return cm

        try:
            ClientSession.post = fake_post  # type: ignore[method-assign]
            result = await conn.upload_file(
                url="https://upload.example.com",
                path=str(test_file),
                type=UploadType.IMAGE,
            )
        finally:
            ClientSession.post = original_post  # type: ignore[method-assign]

        assert result == "ok"
        assert len(created) == 1
        assert created[0].closed is True
        assert connector.closed is False

        await connector.close()

    async def test_default_connector_is_closed_with_session(
        self, mock_bot_token
    ):
        """Собственный дефолтный коннектор закрывается вместе с сессией."""
        bot = Bot(token=mock_bot_token)

        session = await bot.ensure_session()
        connector = session.connector
        assert connector is not None

        await bot.close_session()

        assert connector.closed is True


class TestUnauthorizedDoesNotCloseSession:
    """401 не трогает разделяемую сессию."""

    @pytest.fixture
    def bot_with_mock_session(self, mock_bot_token):
        """Бот с мок-сессией, отслеживающей close()."""
        bot = Bot(token=mock_bot_token)
        session = MagicMock()
        session.closed = False
        session.close = AsyncMock()
        bot.session = session
        return bot

    async def test_session_not_closed_on_401(self, bot_with_mock_session):
        """Сессия остаётся живой — параллельные запросы не рвутся."""
        bot_with_mock_session.session.request = AsyncMock(
            return_value=_make_401()
        )

        conn = BaseConnection()
        conn.bot = bot_with_mock_session

        with pytest.raises(InvalidToken):
            await conn.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        bot_with_mock_session.session.close.assert_not_called()
        assert bot_with_mock_session.session.closed is False

    async def test_401_body_lands_in_exception(self, bot_with_mock_session):
        """Тело ответа 401 попадает в текст InvalidToken."""
        raw = {"code": "verify.token", "message": "invalid access_token"}
        response = _make_401(json_data=raw)
        bot_with_mock_session.session.request = AsyncMock(
            return_value=response
        )

        conn = BaseConnection()
        conn.bot = bot_with_mock_session

        with pytest.raises(InvalidToken) as exc_info:
            await conn.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        message = str(exc_info.value)
        assert "Неверный токен!" in message
        assert "invalid access_token" in message
        response.release.assert_called_once()

    async def test_401_non_json_body_does_not_break(
        self, bot_with_mock_session
    ):
        """Не-JSON тело 401 не подменяет InvalidToken другой ошибкой."""
        response = _make_401(text="<html>403 Forbidden</html>")
        bot_with_mock_session.session.request = AsyncMock(
            return_value=response
        )

        conn = BaseConnection()
        conn.bot = bot_with_mock_session

        with pytest.raises(InvalidToken) as exc_info:
            await conn.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert "403 Forbidden" in str(exc_info.value)

    async def test_401_unreadable_body_keeps_plain_message(
        self, bot_with_mock_session
    ):
        """Нечитаемое тело 401 оставляет сообщение без диагностики."""
        response = _make_401()
        response.text = AsyncMock(side_effect=OSError("boom"))
        bot_with_mock_session.session.request = AsyncMock(
            return_value=response
        )

        conn = BaseConnection()
        conn.bot = bot_with_mock_session

        with pytest.raises(InvalidToken) as exc_info:
            await conn.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert str(exc_info.value) == "Неверный токен!"

    async def test_401_scalar_json_body_is_wrapped(
        self, bot_with_mock_session
    ):
        """Не-объектный JSON в теле 401 оборачивается в {"error": ...}."""
        response = _make_401(json_data="access_token is revoked")
        bot_with_mock_session.session.request = AsyncMock(
            return_value=response
        )

        dispatcher = MagicMock()
        dispatcher.handle_raw_response = AsyncMock()
        bot_with_mock_session.dispatcher = dispatcher

        conn = BaseConnection()
        conn.bot = bot_with_mock_session

        with pytest.raises(InvalidToken) as exc_info:
            await conn.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert "access_token is revoked" in str(exc_info.value)

        await _drain_tasks()

        dispatcher.handle_raw_response.assert_awaited_once_with(
            UpdateType.RAW_API_RESPONSE,
            {"error": "access_token is revoked"},
        )

    async def test_401_json_null_body_keeps_plain_message(
        self, bot_with_mock_session
    ):
        """Тело `null` не превращается в {"error": None}."""
        response = _make_401(json_data=None)
        response.json = AsyncMock(return_value=None)
        bot_with_mock_session.session.request = AsyncMock(
            return_value=response
        )

        conn = BaseConnection()
        conn.bot = bot_with_mock_session

        with pytest.raises(InvalidToken) as exc_info:
            await conn.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert str(exc_info.value) == "Неверный токен!"

    async def test_401_notifies_raw_response_subscribers(
        self, bot_with_mock_session
    ):
        """Для 401 вызывается handle_raw_response, как и для прочих ошибок."""
        raw = {"code": "verify.token", "message": "invalid access_token"}
        bot_with_mock_session.session.request = AsyncMock(
            return_value=_make_401(json_data=raw)
        )

        dispatcher = MagicMock()
        dispatcher.handle_raw_response = AsyncMock()
        bot_with_mock_session.dispatcher = dispatcher

        conn = BaseConnection()
        conn.bot = bot_with_mock_session

        with pytest.raises(InvalidToken):
            await conn.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        # handle_raw_response планируется задачей — даём ей отработать
        await _drain_tasks()

        dispatcher.handle_raw_response.assert_awaited_once_with(
            UpdateType.RAW_API_RESPONSE, raw
        )


class TestFetchResponseSessionResolution:
    """_fetch_response берёт сессию внутри retry-цикла."""

    async def test_session_resolved_per_attempt(self, mock_bot_token):
        """Сессия запрашивается на каждой попытке, а не один раз до цикла."""
        bot = Bot(
            token=mock_bot_token,
            default_connection=DefaultConnectionProperties(
                max_retries=2,
                retry_backoff_factor=0.001,
            ),
        )

        ok = MagicMock()
        ok.status = 200
        ok.ok = True

        retryable = MagicMock()
        retryable.status = 503
        retryable.ok = False
        retryable.read = AsyncMock()

        sessions = []

        def make_session(responses):
            session = MagicMock()
            session.closed = False
            session.request = AsyncMock(side_effect=responses)
            return session

        first = make_session([retryable])
        second = make_session([ok])
        sessions.extend([first, second])

        calls = {"n": 0}

        async def ensure_session():
            session = sessions[min(calls["n"], len(sessions) - 1)]
            calls["n"] += 1
            return session

        bot.ensure_session = ensure_session  # type: ignore[method-assign]

        conn = BaseConnection()
        conn.bot = bot

        response = await conn._fetch_response("https://example.com/file")

        assert response is ok
        assert calls["n"] == 2
        first.request.assert_awaited_once()
        second.request.assert_awaited_once()


class TestClosedSessionIsRetryable:
    """Закрытая на лету сессия не выпускает голый RuntimeError."""

    @staticmethod
    def _closed_session():
        """Сессия, отвечающая RuntimeError, как закрытая aiohttp-сессия."""
        session = MagicMock()
        session.closed = True
        session.request = AsyncMock(
            side_effect=RuntimeError("Session is closed")
        )
        return session

    @staticmethod
    def _pin_sessions(bot, sessions):
        """Заставить ensure_session() отдавать заданные сессии по порядку.

        Подменяем сам ensure_session: закрытую сессию он бы заменил
        новой и увёл тест в реальную сеть.
        """
        calls = {"n": 0}

        async def ensure_session():
            session = sessions[min(calls["n"], len(sessions) - 1)]
            calls["n"] += 1
            return session

        bot.ensure_session = ensure_session
        return calls

    async def test_request_wraps_closed_session(self, mock_bot_token):
        """request() отдаёт MaxConnection, а не RuntimeError."""
        bot = Bot(
            token=mock_bot_token,
            default_connection=DefaultConnectionProperties(
                max_retries=1,
                retry_backoff_factor=0.001,
            ),
        )
        closed = self._closed_session()
        calls = self._pin_sessions(bot, [closed])

        conn = BaseConnection()
        conn.bot = bot

        with pytest.raises(MaxConnection):
            await conn.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        # max_retries=1 — исходная попытка плюс один ретрай
        assert calls["n"] == 2

    async def test_request_retries_on_reopened_session(self, mock_bot_token):
        """Следующая попытка идёт уже через свежую сессию."""
        bot = Bot(
            token=mock_bot_token,
            default_connection=DefaultConnectionProperties(
                max_retries=1,
                retry_backoff_factor=0.001,
            ),
        )

        ok = MagicMock()
        ok.status = 200
        ok.ok = True
        ok.json = AsyncMock(return_value={"success": True})

        alive = MagicMock()
        alive.closed = False
        alive.request = AsyncMock(return_value=ok)

        calls = self._pin_sessions(bot, [self._closed_session(), alive])

        conn = BaseConnection()
        conn.bot = bot

        result = await conn.request(
            method=HTTPMethod.GET,
            path="/test",
            is_return_raw=True,
        )

        assert result == {"success": True}
        assert calls["n"] == 2

    async def test_download_wraps_closed_session(self, mock_bot_token):
        """_fetch_response() отдаёт DownloadFileError, а не RuntimeError."""
        bot = Bot(
            token=mock_bot_token,
            default_connection=DefaultConnectionProperties(
                max_retries=0,
            ),
        )
        self._pin_sessions(bot, [self._closed_session()])

        conn = BaseConnection()
        conn.bot = bot

        with pytest.raises(DownloadFileError):
            await conn._fetch_response("https://example.com/file")

    async def test_runtime_error_on_live_session_propagates(
        self, mock_bot_token
    ):
        """RuntimeError живой сессии не маскируется под сетевую ошибку."""
        bot = Bot(token=mock_bot_token)
        session = MagicMock()
        session.closed = False
        session.request = AsyncMock(side_effect=RuntimeError("что-то ещё"))
        bot.session = session

        conn = BaseConnection()
        conn.bot = bot

        with pytest.raises(RuntimeError, match="что-то ещё"):
            await conn.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )


class TestInvalidTokenMessageIsBounded:
    """Тело 401 не утекает в лог целиком."""

    async def test_huge_body_is_truncated(self, mock_bot_token):
        """Многокилобайтная страница обрезается в тексте исключения."""
        bot = Bot(token=mock_bot_token)
        session = MagicMock()
        session.closed = False
        huge = "x" * 100_000
        session.request = AsyncMock(return_value=_make_401(text=huge))
        bot.session = session

        conn = BaseConnection()
        conn.bot = bot

        with pytest.raises(InvalidToken) as exc_info:
            await conn.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        message = str(exc_info.value)
        assert len(message) < 1000
        assert message.endswith("…")

    async def test_full_body_still_reaches_subscribers(self, mock_bot_token):
        """Подписчики RAW_API_RESPONSE получают тело без усечения."""
        bot = Bot(token=mock_bot_token)
        session = MagicMock()
        session.closed = False
        huge = "x" * 100_000
        session.request = AsyncMock(return_value=_make_401(text=huge))
        bot.session = session

        dispatcher = MagicMock()
        dispatcher.handle_raw_response = AsyncMock()
        bot.dispatcher = dispatcher

        conn = BaseConnection()
        conn.bot = bot

        with pytest.raises(InvalidToken):
            await conn.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        await _drain_tasks()

        dispatcher.handle_raw_response.assert_awaited_once_with(
            UpdateType.RAW_API_RESPONSE, {"error": huge}
        )
