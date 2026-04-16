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
    url=None,
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

    if url is not None:
        mock_response.url = url
        
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
            url="https://example.com/file.pdf",
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
            url="https://example.com/img",
            content_type="image/jpeg",
            chunks=[b"imagedata"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url="https://example.com/img",
            destination=tmp_dir,
        )
        assert result.name == "img.jpg"
        assert result.parent == tmp_dir

    async def test_download_file_no_content_disposition_no_path(
        self, bot, tmp_dir, mock_session
    ):
        """Скачивание без Content-Disposition и без MIME и без внятного пути"""
        from datetime import datetime

        mock_response = _make_mock_response(
            url="https://example.com/",
            chunks=[b"imagedata"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url="https://example.com/",
            destination=tmp_dir,
        )
        expected = f"{datetime.now().strftime("%y%m%d_%H%M%S")}.bin"
        assert result.name == expected
        assert result.parent == tmp_dir


    async def test_download_photo(
        self, bot, tmp_dir, mock_session
    ):
        """Скачивание фложения-фото по ссылке выда https://i.oneme.ru/i?r=photo_token"""
        from datetime import datetime

        mock_response = _make_mock_response(
            url="https://i.oneme.ru/i?r=photo_token",
            content_type="image/jpeg",
            chunks=[b"imagedata"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url="https://i.oneme.ru/i?r=photo_token",
            destination=tmp_dir,
        )
        expected = f"image_{datetime.now().strftime("%y%m%d_%H%M%S")}.jpg"
        assert result.name == expected
        assert result.parent == tmp_dir

    async def test_download_file_path_traversal_protection(
        self, bot, tmp_dir, mock_session
    ):
        """Защита от path traversal в filename."""
        mock_response = _make_mock_response(
            url="https://example.com/file",
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
            url="https://example.com/file",
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

# tests/test_download_file.py

class TestDownloadFileAsBytes:
    """
    Тесты для метода download_file_as_bytes.

    Примеры реальных URL для ручного тестирования:
    - Файл с подписью: 
      https://fd.oneme.ru/getfile?sig=...&expires=...&clientType=3&id=...
    - Изображение: 
      https://i.oneme.ru/i?r=BTGBPUwtwgYUeoFhO7rESmr81n-DnwjHYFhx5_EAhKk...
    """

    async def test_download_file_as_bytes_success(self, bot, mock_session):
        """
        Успешное скачивание файла в память.

        Эмулирует поведение реального эндпоинта типа:
        GET https://fd.oneme.ru/getfile?sig=...&expires=...
        """
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        mock_response = _make_mock_response(
            url="https://fd.oneme.ru/getfile?sig=test&expires=123",
            content_type="application/octet-stream",
            cd_filename="document.pdf",
            chunks=chunks,
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        bio = await bot.download_file_as_bytes(
            url="https://fd.oneme.ru/getfile?sig=test&expires=123",
        )
        result = bio.read()

        assert result == b"chunk1chunk2chunk3"
        mock_response.release.assert_called_once()

    async def test_download_file_as_bytes_image_url(self, bot, mock_session):
        """
        Скачивание изображения с i.oneme.ru.

        Пример реального URL:
        https://i.oneme.ru/i?r=BTGBPUwtwgYUeoFhO7rESmr81n-DnwjHYFhx5_EAhKk...
        """
        # Эмулируем PNG-изображение (минимальный валидный заголовок)
        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_response = _make_mock_response(
            url="https://i.oneme.ru/i?r=test_token",
            content_type="image/png",
            chunks=[png_header],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        bio = await bot.download_file_as_bytes(
            url="https://i.oneme.ru/i?r=test_token",
        )
        result = bio.read()

        assert result.startswith(b"\x89PNG")
        assert len(result) > 0


    async def test_download_file_as_bytes_http_error(self, bot, mock_session):
        """DownloadFileError при HTTP 404."""
        mock_response = _make_mock_response(ok=False, status=404)
        mock_session.request = AsyncMock(return_value=mock_response)

        with pytest.raises(DownloadFileError, match="HTTP 404"):
            await bot.download_file_as_bytes(
                url="https://example.com/missing",
            )

    async def test_download_file_as_bytes_connection_error(
        self, bot, mock_session
    ):
        """DownloadFileError при ошибке соединения."""
        from aiohttp import ClientConnectionError

        mock_session.request = AsyncMock(
            side_effect=ClientConnectionError("timeout")
        )
        bot.default_connection.max_retries = 0

        with pytest.raises(DownloadFileError, match="Ошибка при скачивании"):
            await bot.download_file_as_bytes(
                url="https://example.com/file",
            )

    async def test_download_file_as_bytes_retry_on_503(
        self, bot, mock_session
    ):
        """Retry при 503, затем успех."""
        retry_response = _make_mock_response(ok=False, status=503)
        retry_response.read = AsyncMock()

        success_response = _make_mock_response(
            url="https://example.com/file",
            content_type="text/plain",
            chunks=[b"success"],
        )

        mock_session.request = AsyncMock(
            side_effect=[retry_response, success_response]
        )
        bot.default_connection.max_retries = 1
        bot.default_connection.retry_backoff_factor = 0.0

        with patch("asyncio.sleep", new_callable=AsyncMock):
            bio = await bot.download_file_as_bytes(
                url="https://example.com/file",
            )
            result = bio.read()
            assert result == b"success"

    async def test_download_file_as_bytes_empty_file(self, bot, mock_session):
        """Скачивание пустого файла."""
        mock_response = _make_mock_response(
            url="https://example.com/empty",
            content_type="application/octet-stream",
            chunks=[],  # Пустой итератор
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        bio = await bot.download_file_as_bytes(
            url="https://example.com/empty",
        )
        result = bio.read()
        assert result == b""

    async def test_download_file_vs_as_bytes_same_content(
        self, bot, tmp_dir, mock_session
    ):
        """download_file и download_file_as_bytes возвращают одинаковые данные."""
        content = b"test content for comparison"
        chunks = [content[i:i+10] for i in range(0, len(content), 10)]

        # Для download_file
        mock_response_disk = _make_mock_response(
            url="https://example.com/file",
            cd_filename="test.txt",
            chunks=chunks.copy(),
        )
        # Для download_file_as_bytes
        mock_response_bytes = _make_mock_response(
            url="https://example.com/file",
            cd_filename="test.txt",
            chunks=chunks.copy(),
        )

        # Мокаем request дважды: первый вызов — для disk, второй — для bytes
        mock_session.request = AsyncMock(
            side_effect=[mock_response_disk, mock_response_bytes]
        )

        # Скачиваем на диск
        path = await bot.download_file(
            url="https://example.com/file",
            destination=tmp_dir,
        )
        disk_content = path.read_bytes()

        # Скачиваем в память
        bio = await bot.download_file_as_bytes(
            url="https://example.com/file",
        )
        bytes_content = bio.read()

        assert path.name == bio.name
        assert disk_content == bytes_content == content


    async def test_download_file_name_collision(self, bot, tmp_dir, mock_session):
        """Проверка, что при коллизии имён добавляется (2), (3) и т.д."""
        from typing import List
        from pathlib import Path

        # Пытаемся скачать сразу 5 файлов
        results: List[Path] = []
        for i in range(5):
            mock_response = _make_mock_response(
                url=f"https://i.oneme.ru/i?r=file{i+1}",
                chunks=[f"new {i+1}".encode()]
            )
            mock_session.request = AsyncMock(return_value=mock_response)
            results.append(
                await bot.download_file(
                    url=f"https://i.oneme.ru/i?r=file{i+1}",
                    destination=tmp_dir,
                )
            )

        for i, result in enumerate(results):
            if i == 0: # Первый файл не проверяем
                # Первый файл должен быть без суффикса _N
                # Только image_date_time
                assert '(' not in result.stem and ')' not in result.stem
            else:
                # Ожидаем, что файлы сохранится с суффиксами
                assert result.stem.endswith(f"({i+1})")
                assert result.read_bytes() == f"new {i+1}".encode()


    async def test_download_file_photo_correct_extension(
        self, bot, tmp_dir, mock_session
    ):
        """Для i.oneme.ru расширение определяется по Content-Type, а не .webp."""
        mock_response = _make_mock_response(
            url="https://i.oneme.ru/i?r=test",
            content_type="image/png",
            chunks=[b"\x89PNG\r\n\x1a\n"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url="https://i.oneme.ru/i?r=test",
            destination=tmp_dir,
        )

        assert result.suffix == ".png"  # не .webp!
        assert result.name.startswith("image_")
