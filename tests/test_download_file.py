"""Тесты для метода download_file."""

from unittest.mock import MagicMock, patch

import pytest
from maxapi.bot import Bot
from maxapi.exceptions.download_file import DownloadFileError
from requests import ConnectionError


@pytest.fixture
def bot():
    return Bot(token="test-token")


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


def _make_mock_response(
    *,
    ok=True,
    status_code=200,
    content_type="application/octet-stream",
    cd_filename=None,
    chunks=None,
):
    """Создаёт мок ответа requests.Response для скачивания."""
    mock_response = MagicMock()
    mock_response.ok = ok
    mock_response.status_code = status_code
    mock_response.headers = {"Content-Type": content_type}

    if cd_filename is not None:
        mock_response.headers["Content-Disposition"] = (
            f'attachment; filename="{cd_filename}"'
        )

    if chunks is not None:
        mock_response.iter_content = MagicMock(return_value=iter(chunks))

    return mock_response


@pytest.fixture
def mock_session(bot):
    """Создаёт мок-сессию и привязывает к боту."""
    session = MagicMock()
    session.closed = False
    bot.session = session
    return session


class TestDownloadFile:
    def test_download_file_success(self, bot, tmp_dir, mock_session):
        """Скачивание файла с корректным Content-Disposition."""
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        mock_response = _make_mock_response(
            content_type="application/pdf",
            cd_filename="document.pdf",
            chunks=chunks,
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_file(
            url="https://example.com/file.pdf",
            destination=tmp_dir,
        )

        assert result == tmp_dir / "document.pdf"
        assert result.read_bytes() == b"chunk1chunk2chunk3"

    def test_download_file_no_content_disposition(
        self, bot, tmp_dir, mock_session
    ):
        """Скачивание без Content-Disposition — имя генерируется по MIME."""
        mock_response = _make_mock_response(
            content_type="image/jpeg",
            chunks=[b"imagedata"],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_file(
            url="https://example.com/img",
            destination=tmp_dir,
        )

        assert result.name.startswith("file")
        assert result.parent == tmp_dir

    def test_download_file_path_traversal_protection(
        self, bot, tmp_dir, mock_session
    ):
        """Защита от path traversal в filename."""
        mock_response = _make_mock_response(
            content_type="text/plain",
            cd_filename="../../etc/passwd",
            chunks=[b"data"],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_file(
            url="https://example.com/file",
            destination=tmp_dir,
        )

        # Только basename, без ../
        assert result.parent == tmp_dir
        assert result.name == "passwd"

    def test_download_file_http_error(self, bot, tmp_dir, mock_session):
        """DownloadFileError при HTTP 404."""
        mock_response = _make_mock_response(ok=False, status_code=404)
        mock_session.get = MagicMock(return_value=mock_response)

        with pytest.raises(DownloadFileError, match="HTTP 404"):
            bot.download_file(
                url="https://example.com/missing",
                destination=tmp_dir,
            )

    def test_download_file_connection_error_raises(
        self, bot, tmp_dir, mock_session
    ):
        """DownloadFileError при исчерпании попыток соединения."""

        mock_session.get = MagicMock(
            side_effect=ConnectionError("connection refused")
        )
        bot.default_connection.max_retries = 0

        with pytest.raises(DownloadFileError, match="Ошибка при скачивании"):
            bot.download_file(
                url="https://example.com/file",
                destination=tmp_dir,
            )

    def test_download_file_retry_on_server_error(
        self, bot, tmp_dir, mock_session
    ):
        """Retry при 503, затем успех."""
        retry_response = _make_mock_response(ok=False, status_code=503)

        success_response = _make_mock_response(
            content_type="text/plain",
            cd_filename="result.txt",
            chunks=[b"ok"],
        )

        mock_session.get = MagicMock(
            side_effect=[retry_response, success_response]
        )
        bot.default_connection.max_retries = 1
        bot.default_connection.retry_backoff_factor = 0.0

        with patch("time.sleep"):
            result = bot.download_file(
                url="https://example.com/file",
                destination=tmp_dir,
            )

        assert result.name == "result.txt"
