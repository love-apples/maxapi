"""Тесты для метода download_file."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from maxapi.bot import Bot
from maxapi.exceptions.download_file import DownloadFileError


@pytest.fixture
def bot():
    return Bot(token="test-token")


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


class AsyncIterator:
    """Хелпер для создания async iterator из списка."""

    def __init__(self, items):
        self.items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.items)
        except StopIteration:
            raise StopAsyncIteration from None


def _make_mock_response(
    *,
    ok=True,
    status=200,
    content_type="application/octet-stream",
    cd_filename=None,
    chunks=None,
):
    """Создаёт мок aiohttp-ответа для скачивания."""
    mock_response = AsyncMock()
    mock_response.ok = ok
    mock_response.status = status
    mock_response.content_type = content_type

    if cd_filename is not None:
        cd = MagicMock()
        cd.filename = cd_filename
        mock_response.content_disposition = cd
    else:
        mock_response.content_disposition = None

    if chunks is not None:
        mock_response.content.iter_chunked = MagicMock(
            return_value=AsyncIterator(chunks)
        )

    return mock_response


@pytest.fixture
def mock_session(bot):
    """Создаёт мок-сессию и привязывает к боту."""
    session = AsyncMock()
    session.closed = False
    bot.session = session
    return session


class TestDownloadFile:
    async def test_download_file_success(self, bot, tmp_dir, mock_session):
        """Скачивание файла с корректным Content-Disposition."""
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        mock_response = _make_mock_response(
            content_type="application/pdf",
            cd_filename="document.pdf",
            chunks=chunks,
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url="https://example.com/file.pdf",
            destination=tmp_dir,
        )

        assert result == tmp_dir / "document.pdf"
        assert result.read_bytes() == b"chunk1chunk2chunk3"

    async def test_download_file_no_content_disposition(
        self, bot, tmp_dir, mock_session
    ):
        """Скачивание без Content-Disposition — имя генерируется по MIME."""
        mock_response = _make_mock_response(
            content_type="image/jpeg",
            chunks=[b"imagedata"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url="https://example.com/img",
            destination=tmp_dir,
        )

        assert result.name.startswith("file")
        assert result.parent == tmp_dir

    async def test_download_file_path_traversal_protection(
        self, bot, tmp_dir, mock_session
    ):
        """Защита от path traversal в filename."""
        mock_response = _make_mock_response(
            content_type="text/plain",
            cd_filename="../../etc/passwd",
            chunks=[b"data"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url="https://example.com/file",
            destination=tmp_dir,
        )

        # Только basename, без ../
        assert result.parent == tmp_dir
        assert result.name == "passwd"

    async def test_download_file_http_error(self, bot, tmp_dir, mock_session):
        """DownloadFileError при HTTP 404."""
        mock_response = _make_mock_response(ok=False, status=404)
        mock_session.request = AsyncMock(return_value=mock_response)

        with pytest.raises(DownloadFileError, match="HTTP 404"):
            await bot.download_file(
                url="https://example.com/missing",
                destination=tmp_dir,
            )

    async def test_download_file_connection_error_raises(
        self, bot, tmp_dir, mock_session
    ):
        """DownloadFileError при исчерпании попыток соединения."""
        from aiohttp import ClientConnectionError

        mock_session.request = AsyncMock(
            side_effect=ClientConnectionError("connection refused")
        )
        bot.default_connection.max_retries = 0

        with pytest.raises(DownloadFileError, match="Ошибка при скачивании"):
            await bot.download_file(
                url="https://example.com/file",
                destination=tmp_dir,
            )

    async def test_download_file_retry_on_server_error(
        self, bot, tmp_dir, mock_session
    ):
        """Retry при 503, затем успех."""
        retry_response = _make_mock_response(ok=False, status=503)
        retry_response.read = AsyncMock()

        success_response = _make_mock_response(
            content_type="text/plain",
            cd_filename="result.txt",
            chunks=[b"ok"],
        )

        mock_session.request = AsyncMock(
            side_effect=[retry_response, success_response]
        )
        bot.default_connection.max_retries = 1
        bot.default_connection.retry_backoff_factor = 0.0

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await bot.download_file(
                url="https://example.com/file",
                destination=tmp_dir,
            )

        assert result.name == "result.txt"

    async def test_ensure_session_creates_new(self, bot):
        """ensure_session создаёт сессию если её нет."""
        bot.session = None

        with patch(
            "maxapi.bot.ClientSession", autospec=True
        ) as MockClientSession:
            mock_session_instance = AsyncMock()
            mock_session_instance.closed = False
            MockClientSession.return_value = mock_session_instance

            session = await bot.ensure_session()

        assert session is mock_session_instance
        MockClientSession.assert_called_once()

    async def test_ensure_session_reuses_existing(self, bot, mock_session):
        """ensure_session возвращает существующую сессию."""
        session = await bot.ensure_session()
        assert session is mock_session
