"""Тесты обработки ответов в BaseConnection (issue #199)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from maxapi import Bot
from maxapi.client.default import DefaultConnectionProperties
from maxapi.connection.base import BaseConnection
from maxapi.enums.http_method import HTTPMethod
from maxapi.enums.update import UpdateType
from maxapi.enums.upload_type import UploadType
from maxapi.exceptions.max import MaxApiError, MaxUploadFileFailed

HTML_ERROR_BODY = "<html><body><h1>429 Too Many Requests</h1></body></html>"


def _make_response(status, *, text=""):
    """Создаёт мок aiohttp-ответа с async-методами."""
    resp = MagicMock()
    resp.status = status
    resp.ok = 200 <= status < 300
    resp.read = AsyncMock()
    resp.text = AsyncMock(return_value=text)
    return resp


def _make_bot_with_response(mock_bot_token, response, **conn_kwargs):
    """Бот с мок-сессией, всегда отдающей переданный ответ."""
    bot = Bot(
        token=mock_bot_token,
        default_connection=DefaultConnectionProperties(**conn_kwargs),
    )
    session = MagicMock()
    session.closed = False
    session.close = AsyncMock()
    session.request = AsyncMock(return_value=response)
    bot.session = session
    return bot


def _make_upload_connection(response):
    """BaseConnection с ботом и сессией, отдающей переданный ответ."""
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = response
    mock_cm.__aexit__.return_value = False

    session = MagicMock()
    session.closed = False
    session.post = Mock(return_value=mock_cm)

    conn = BaseConnection()
    bot = Mock()
    bot.default_connection = DefaultConnectionProperties()
    bot.session = session
    conn.bot = bot
    return conn


def _make_upload_response(status, *, text=""):
    """Мок ответа upload-сервера.

    ``ok`` повторяет семантику aiohttp (status < 400), чтобы тесты
    ловили ошибочную трактовку 3xx как успешной загрузки.
    """
    resp = MagicMock()
    resp.status = status
    resp.ok = status < 400
    resp.text = AsyncMock(return_value=text)
    return resp


class TestUploadFileStatusCheck:
    """Дефект 1: статус ответа upload-сервера проверяется."""

    @pytest.mark.asyncio
    async def test_upload_file_raises_on_error_status(self, tmp_path):
        """upload_file бросает MaxUploadFileFailed при 413."""
        test_file = tmp_path / "big.mp4"
        test_file.write_bytes(b"fake-video")

        response = _make_upload_response(413, text="Request Entity Too Large")
        conn = _make_upload_connection(response)

        with pytest.raises(MaxUploadFileFailed) as exc_info:
            await conn.upload_file(
                url="https://upload.example.com",
                path=str(test_file),
                type=UploadType.VIDEO,
            )

        message = str(exc_info.value)
        assert "413" in message
        assert "Request Entity Too Large" in message

    @pytest.mark.asyncio
    async def test_upload_file_buffer_raises_on_error_status(self):
        """upload_file_buffer бросает MaxUploadFileFailed при 500."""
        response = _make_upload_response(500, text="upload backend down")
        conn = _make_upload_connection(response)

        with pytest.raises(MaxUploadFileFailed) as exc_info:
            await conn.upload_file_buffer(
                filename="clip",
                url="https://upload.example.com",
                buffer=b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 100,
                type=UploadType.AUDIO,
            )

        message = str(exc_info.value)
        assert "500" in message
        assert "upload backend down" in message

    @pytest.mark.asyncio
    async def test_upload_file_temp_session_raises_on_error_status(
        self, tmp_path
    ):
        """Ветка временной сессии в upload_file тоже проверяет статус."""
        test_file = tmp_path / "doc.pdf"
        test_file.write_bytes(b"fake-pdf")

        response = _make_upload_response(413, text="too large")

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = response
        mock_cm.__aexit__.return_value = False

        temp_session = AsyncMock()
        temp_session.post = Mock(return_value=mock_cm)

        conn = BaseConnection()
        bot = Mock()
        bot.default_connection = DefaultConnectionProperties()
        bot.session = None
        conn.bot = bot

        with patch("maxapi.connection.base.ClientSession") as mock_cs_cls:
            mock_cs_cls.return_value.__aenter__ = AsyncMock(
                return_value=temp_session
            )
            mock_cs_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(MaxUploadFileFailed) as exc_info:
                await conn.upload_file(
                    url="https://upload.example.com",
                    path=str(test_file),
                    type=UploadType.FILE,
                )

        assert "413" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_file_buffer_temp_session_raises_on_error_status(
        self,
    ):
        """Ветка временной сессии в upload_file_buffer проверяет статус."""
        response = _make_upload_response(502, text="bad gateway")

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = response
        mock_cm.__aexit__.return_value = False

        temp_session = AsyncMock()
        temp_session.post = Mock(return_value=mock_cm)

        conn = BaseConnection()
        bot = Mock()
        bot.default_connection = DefaultConnectionProperties()
        bot.session = None
        conn.bot = bot

        with patch("maxapi.connection.base.ClientSession") as mock_cs_cls:
            mock_cs_cls.return_value.__aenter__ = AsyncMock(
                return_value=temp_session
            )
            mock_cs_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(MaxUploadFileFailed) as exc_info:
                await conn.upload_file_buffer(
                    filename="clip",
                    url="https://upload.example.com",
                    buffer=b"%PDF-1.4\n" + b"\x00" * 100,
                    type=UploadType.FILE,
                )

        assert "502" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_file_raises_on_redirect_status(self, tmp_path):
        """3xx от upload-сервера не считается успешной загрузкой."""
        test_file = tmp_path / "photo.png"
        test_file.write_bytes(b"fake-png")

        response = _make_upload_response(302, text="Found")
        conn = _make_upload_connection(response)

        with pytest.raises(MaxUploadFileFailed) as exc_info:
            await conn.upload_file(
                url="https://upload.example.com",
                path=str(test_file),
                type=UploadType.IMAGE,
            )

        assert "302" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_file_returns_body_on_success(self, tmp_path):
        """При успешном статусе возвращается сырое тело ответа."""
        test_file = tmp_path / "photo.png"
        test_file.write_bytes(b"fake-png")

        response = _make_upload_response(200, text='{"token":"t"}')
        conn = _make_upload_connection(response)

        result = await conn.upload_file(
            url="https://upload.example.com",
            path=str(test_file),
            type=UploadType.IMAGE,
        )

        assert result == '{"token":"t"}'


class TestRequestNonJsonBody:
    """Дефект 2: не-JSON тело не роняет request() голым aiohttp."""

    @pytest.mark.asyncio
    async def test_html_error_body_raises_max_api_error(self, mock_bot_token):
        """text/html при 429 заворачивается в MaxApiError."""
        response = _make_response(429, text=HTML_ERROR_BODY)
        bot = _make_bot_with_response(mock_bot_token, response)

        base = BaseConnection()
        base.bot = bot

        with pytest.raises(MaxApiError) as exc_info:
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert exc_info.value.code == 429
        assert exc_info.value.raw == HTML_ERROR_BODY

    @pytest.mark.asyncio
    async def test_empty_error_body_raises_max_api_error(self, mock_bot_token):
        """Пустое тело при 400 не роняет request()."""
        response = _make_response(400, text="")
        bot = _make_bot_with_response(mock_bot_token, response)

        base = BaseConnection()
        base.bot = bot

        with pytest.raises(MaxApiError) as exc_info:
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert exc_info.value.code == 400
        assert exc_info.value.raw == ""

    @pytest.mark.asyncio
    async def test_json_error_body_parsed_to_dict(self, mock_bot_token):
        """JSON-тело ошибки по-прежнему попадает в raw как dict."""
        response = _make_response(400, text='{"code": "attachment.not.ready"}')
        bot = _make_bot_with_response(mock_bot_token, response)

        base = BaseConnection()
        base.bot = bot

        with pytest.raises(MaxApiError) as exc_info:
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert exc_info.value.raw == {"code": "attachment.not.ready"}


class TestRequestOkBodySemantics:
    """Дефект 2: пустое/не-dict тело успешного ответа."""

    @pytest.mark.asyncio
    async def test_empty_ok_body_raises_max_api_error(self, mock_bot_token):
        """Пустое тело при 200 даёт MaxApiError, а не TypeError."""
        response = _make_response(200, text="")
        bot = _make_bot_with_response(mock_bot_token, response)

        base = BaseConnection()
        base.bot = bot

        with pytest.raises(MaxApiError) as exc_info:
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                model=MagicMock(),
            )

        assert exc_info.value.code == 200
        assert exc_info.value.raw == ""

    @pytest.mark.asyncio
    async def test_non_dict_ok_body_raises_max_api_error(self, mock_bot_token):
        """JSON-массив при 200 даёт MaxApiError с текстом тела."""
        response = _make_response(200, text="[1, 2, 3]")
        bot = _make_bot_with_response(mock_bot_token, response)

        base = BaseConnection()
        base.bot = bot

        with pytest.raises(MaxApiError) as exc_info:
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert exc_info.value.code == 200
        assert exc_info.value.raw == "[1, 2, 3]"

    @pytest.mark.asyncio
    async def test_ok_body_never_calls_model_on_bad_body(self, mock_bot_token):
        """model не вызывается, если тело не является JSON-объектом."""
        response = _make_response(200, text="not json at all")
        bot = _make_bot_with_response(mock_bot_token, response)

        base = BaseConnection()
        base.bot = bot
        model = MagicMock()

        with pytest.raises(MaxApiError):
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                model=model,
            )

        model.assert_not_called()


class TestRetryExhaustedKeepsBody:
    """Дефект 3: тело серверной ошибки не теряется после ретраев."""

    @pytest.fixture
    def conn_kwargs(self):
        """Быстрый retry для тестов."""
        return {
            "max_retries": 2,
            "retry_on_statuses": (502, 503, 504),
            "retry_backoff_factor": 0.01,
        }

    @pytest.mark.asyncio
    async def test_json_body_preserved_as_dict(
        self, mock_bot_token, conn_kwargs
    ):
        """JSON-тело 503 попадает в MaxApiError.raw как dict."""
        response = _make_response(503, text='{"code": "service.unavailable"}')
        bot = _make_bot_with_response(mock_bot_token, response, **conn_kwargs)

        base = BaseConnection()
        base.bot = bot

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(MaxApiError) as exc_info,
        ):
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert exc_info.value.code == 503
        assert exc_info.value.raw == {"code": "service.unavailable"}
        assert exc_info.value.raw != {"error": "Server error 503"}

    @pytest.mark.asyncio
    async def test_html_body_preserved_as_text(
        self, mock_bot_token, conn_kwargs
    ):
        """Не-JSON тело 502 попадает в MaxApiError.raw как текст."""
        body = "<html><body><h1>502 Bad Gateway</h1></body></html>"
        response = _make_response(502, text=body)
        bot = _make_bot_with_response(mock_bot_token, response, **conn_kwargs)

        base = BaseConnection()
        base.bot = bot

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
        assert exc_info.value.raw == body

    @pytest.mark.asyncio
    async def test_raw_response_dispatched_after_retries(
        self, mock_bot_token, conn_kwargs
    ):
        """После исчерпания ретраев вызывается handle_raw_response."""
        response = _make_response(503, text='{"code": "service.unavailable"}')
        bot = _make_bot_with_response(mock_bot_token, response, **conn_kwargs)
        bot.dispatcher = SimpleNamespace(handle_raw_response=AsyncMock())

        base = BaseConnection()
        base.bot = bot

        created = []

        def fake_create_task(coro):
            coro.close()
            created.append(coro)

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("asyncio.create_task", side_effect=fake_create_task),
            pytest.raises(MaxApiError),
        ):
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert len(created) == 1
        # AsyncMock фиксирует аргументы в момент вызова, до await —
        # проверяем и тип события, и распарсенное тело
        bot.dispatcher.handle_raw_response.assert_called_once_with(
            UpdateType.RAW_API_RESPONSE,
            {"code": "service.unavailable"},
        )


class TestUnreadableBody:
    """Сбой чтения тела: ответ освобождается, исключения — из SDK."""

    @pytest.mark.asyncio
    async def test_request_releases_response_on_read_failure(
        self, mock_bot_token
    ):
        """При сбое text() в request() вызывается release()."""
        response = _make_response(200)
        response.text = AsyncMock(side_effect=RuntimeError("conn lost"))
        bot = _make_bot_with_response(mock_bot_token, response)

        base = BaseConnection()
        base.bot = bot

        with pytest.raises(MaxApiError) as exc_info:
            await base.request(
                method=HTTPMethod.GET,
                path="/test",
                is_return_raw=True,
            )

        assert exc_info.value.code == 200
        assert exc_info.value.raw == ""
        response.release.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_read_failure_raises_upload_failed(self, tmp_path):
        """Сбой чтения ответа upload-сервера даёт MaxUploadFileFailed."""
        test_file = tmp_path / "photo.png"
        test_file.write_bytes(b"fake-png")

        response = _make_upload_response(200)
        response.text = AsyncMock(side_effect=RuntimeError("conn lost"))
        conn = _make_upload_connection(response)

        with pytest.raises(MaxUploadFileFailed) as exc_info:
            await conn.upload_file(
                url="https://upload.example.com",
                path=str(test_file),
                type=UploadType.IMAGE,
            )

        assert "conn lost" in str(exc_info.value)
