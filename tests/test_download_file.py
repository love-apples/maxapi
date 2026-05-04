"""Тесты для метода download_file."""

import inspect
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from aiohttp import ClientResponse
from maxapi.bot import Bot
from maxapi.exceptions.download_file import DownloadFileError
from yarl import URL

REAL_URL_LINKS = {
    "audio": {
        "url": (
            "http://vd624.okcdn.ru/?expires=1777235877381&srcIp=10.205.180.43"
            "&pr=96&srcAg=UNKNOWN&ms=185.180.203.12&type=2&sig=fZchtK7v5ww"
            "&ct=2&urls=176.112.172.22&clientType=11&appId=1248243456&"
            "id=15115318397640&scl=2"
        ),
        "cd_filename": "15115318397640.mp3",
        "content_type": "audio/mpeg",
        "expected": "15115318397640.mp3",
    },
    "image": {
        "url": (
            "https://i.oneme.ru/i?r="
            "BTGBPUwtwgYUeoFhO7rESmr8"  # head
            "1n-DnwjHYFhx5_EAhKk7Np"  # unique_part
            "BwxbPWZMl-nt3whnrS81A"  # tail
        ),
        "cd_filename": None,
        "content_type": "image/webp",
        "expected": "image_1n-DnwjHYFhx5_EAhKk7Ng.webp",
    },
    "image_user_avatar": {
        "url": (
            "https://i.oneme.ru/i?r="
            "BUFglOvkF6bn--g5U-BFgIkJ"  # head
            "K6mx6ae5OiOa8c66MUn6oXkSMPFAFZx509DvRP7Cxt1"  # unique_part
            "44dcdJWD0pBaSRiPxZ0Ss"  # tail
        ),
        "cd_filename": None,
        "content_type": "image/webp",
        "expected": "image_K6mx6ae5OiOa8c66MUn6oXkSMPFAFZx509DvRP7Cxt0.webp",
    },
    "sticker": {
        "url": "https://i.oneme.ru/getSmile?smileId=c1453bbb&smileType=4",
        "cd_filename": None,
        "content_type": "image/png",
        "expected": "sticker_c1453bbb.png",
    },
    "file": {
        "url": (
            "https://fd.oneme.ru/getfile?sig=DmSN4pnkY6CxxF2-"
            "VDxpsKJfw7AZy8m9qV2ynnU6IqIAS6kiJIV39Bq3D8XZ9Ut4WOhDSRfyhSCmvNhzHZDpGg"
            "&expires=1778011573929&clientType=3&id=3118979750&userId=251973343"
        ),
        "cd_filename": "205046_55821186.jpeg",
        "content_type": "application/octet-stream",
        "expected": "205046_55821186.jpeg",
    },
    "video": {
        "url": (
            "https://vd545.okcdn.ru/?expires=1777181558195&srcIp=127.0.0.1"
            "&pr=95&srcAg=UNKNOWN&ms=123.456.78.90&type=3&sig=mJM_Fry0PSY"
            "&ct=0&urls=10.145.67.89&clientType=11&appId=1234567890"
            "&id=12345678901234&scl=1"
        ),
        "cd_filename": "12345678901234.mp4",
        "content_type": "video/mp4",
        "expected": "12345678901234.mp4",
    },
    # "thumbnail": (
    #     "https://pimg.mycdn.me/getImage?disableStub=true"
    #     "&type=PREPARE&url=https%3A%2F%2Fiv.okcdn.ru%2F"
    #     "videoPreview%3Fid%3D15054635666120%26type%3D39%26idx"
    #     "%3D0%26scl%3D2%26tkn%3Dt-XIJ6RzOp2je0aLFQX3rkMuTkY"
    #     "&signatureToken=xH6_Hq_03SyJsP_ZsL_UAQ"
    # ),
    # url link not works yet
}


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
    closed=False,
):
    """Создаёт мок aiohttp-ответа для скачивания."""
    mock_response = AsyncMock(spec_set=ClientResponse)
    mock_response.ok = ok
    mock_response.release = Mock(
        side_effect=lambda: setattr(mock_response, "closed", True)
    )
    mock_response.closed = closed
    mock_response.status = status
    mock_response.content_type = content_type
    mock_response.__class__ = ClientResponse  # type: ignore

    if cd_filename is not None:
        cd = MagicMock()
        cd.filename = cd_filename
        mock_response.content_disposition = cd
    else:
        mock_response.content_disposition = None

    if url is not None:
        mock_response.url = URL(url)
    else:
        mock_response.url = URL()

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


def freeze_datetime(
    target_module: str, fixed_dt: datetime | str, *, attr: str = "datetime"
) -> Callable:
    """
    Декоратор для заморозки datetime.now() в указанном модуле.
    Корректно работает с синхронными и асинхронными тестами.

    Args:
        target_module: Полный путь к модулю, где вызывается datetime.now()
                       (например: 'myapp.services.payment', 'tests.conftest')
        fixed_dt: Фиксированная дата/время (datetime объект или ISO-строка)
        attr: Имя атрибута для патча.
            'datetime'          → если в модуле `from datetime import datetime`
            'datetime.datetime' → если в модуле `import datetime`

    Returns:
        Декоратор для тестовой функции.
    """
    if isinstance(fixed_dt, str):
        fixed_dt = datetime.fromisoformat(fixed_dt)

    patch_target = f"{target_module}.{attr}"

    def decorator(func: Callable) -> Callable:
        # Синхронная обёртка
        @wraps(func)
        def _sync_wrapper(*args, **kwargs):
            with patch(patch_target) as mock_dt:
                mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
                mock_dt.now.return_value = fixed_dt
                return func(*args, **kwargs)

        # Асинхронная обёртка
        @wraps(func)
        async def _async_wrapper(*args, **kwargs):
            with patch(patch_target) as mock_dt:
                mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
                mock_dt.now.return_value = fixed_dt
                return await func(*args, **kwargs)

        # Возвращаем нужную обёртку в зависимости от типа функции
        if inspect.iscoroutinefunction(func):
            return _async_wrapper
        else:
            return _sync_wrapper

    return decorator


class TestDownloadFile:
    async def test_download_file_path_as_str(self, bot, tmp_dir, mock_session):
        """Скачивание файла с корректным Content-Disposition."""
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        url_case = REAL_URL_LINKS["file"]

        mock_response = _make_mock_response(
            url=url_case["url"],
            chunks=chunks,
            cd_filename=url_case["cd_filename"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url=url_case["url"],
            destination=str(tmp_dir),
        )

        assert result == tmp_dir / url_case["expected"]
        assert result.read_bytes() == b"".join(chunks)

    async def test_download_file_success(self, bot, tmp_dir, mock_session):
        """Скачивание файла с корректным Content-Disposition."""
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        url_case = REAL_URL_LINKS["file"]

        mock_response = _make_mock_response(
            url=url_case["url"],
            content_type=REAL_URL_LINKS["file"]["content_type"],
            cd_filename=url_case["cd_filename"],
            chunks=chunks,
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url=url_case["url"],
            destination=tmp_dir,
        )

        assert result == tmp_dir / url_case["expected"]
        assert result.read_bytes() == b"".join(chunks)

    async def test_download_file_no_content_disposition(
        self, bot, tmp_dir, mock_session
    ):
        """Скачивание без Content-Disposition — имя генерируется по MIME."""
        url = "https://example.com/img"
        mock_response = _make_mock_response(
            url=url,
            content_type="image/jpeg",
            chunks=[b"imagedata"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url=url,
            destination=tmp_dir,
        )
        assert result.name == "img.jpg"
        assert result.parent == tmp_dir

    @freeze_datetime("maxapi.connection.base", "2026-04-16 10:30:50")
    async def test_download_file_no_content_disposition_no_path(
        self, bot, tmp_dir, mock_session
    ):
        """Скачивание без Content-Disposition и без MIME и без внятного пути"""
        url = "https://example.com/"
        mock_response = _make_mock_response(
            url=url,
            content_type=None,  # Без типа # type: ignore
            chunks=[b"some_binary_data"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url=url,
            destination=tmp_dir,
        )

        assert result.name == "260416_103050.bin"
        assert result.parent == tmp_dir

    async def test_download_image(self, bot, tmp_dir, mock_session):
        """Скачивание вложения-изображения"""
        url_case = REAL_URL_LINKS["image"]
        mock_response = _make_mock_response(
            url=url_case["url"],
            content_type=url_case["content_type"],
            chunks=[b"imagedata"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url=url_case["url"],
            destination=tmp_dir,
        )

        assert result.name == url_case["expected"]
        assert result.parent == tmp_dir

    async def test_download_image_user_avatar(
        self, bot, tmp_dir, mock_session
    ):
        """Скачивание вложения-изображения"""
        url_case = REAL_URL_LINKS["image_user_avatar"]
        mock_response = _make_mock_response(
            url=url_case["url"],
            content_type=url_case["content_type"],
            chunks=[b"imagedata"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url=url_case["url"],
            destination=tmp_dir,
        )

        assert result.name == url_case["expected"]
        assert result.parent == tmp_dir

    async def test_download_video(self, bot, tmp_dir, mock_session):
        """Скачивание вложения-видео"""
        url_case = REAL_URL_LINKS["video"]
        mock_response = _make_mock_response(
            url=url_case["url"],
            cd_filename=url_case["cd_filename"],
            content_type=url_case["content_type"],
            chunks=[b"mp4videodata"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url=url_case["url"],
            destination=tmp_dir,
        )

        assert result.name == url_case["cd_filename"]
        assert result.parent == tmp_dir

    async def test_download_audio(self, bot, tmp_dir, mock_session):
        """Скачивание вложения-аудио"""
        url_case = REAL_URL_LINKS["audio"]
        mock_response = _make_mock_response(
            url=url_case["url"],
            cd_filename=url_case["cd_filename"],
            content_type=url_case["content_type"],
            chunks=[b"mp3audiodata"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url=url_case["url"],
            destination=tmp_dir,
        )

        assert result.name == url_case["cd_filename"]
        assert result.parent == tmp_dir

    async def test_download_sticker(self, bot, tmp_dir, mock_session):
        """Скачивание вложения-аудио"""
        url_case = REAL_URL_LINKS["sticker"]
        mock_response = _make_mock_response(
            url=url_case["url"],
            cd_filename=url_case["cd_filename"],
            content_type=url_case["content_type"],
            chunks=[b"PNGdata"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url=url_case["url"],
            destination=tmp_dir,
        )

        assert result.name == url_case["expected"]
        assert result.parent == tmp_dir

    async def test_download_file_path_traversal_protection(
        self, bot, tmp_dir, mock_session
    ):
        """Защита от path traversal в filename."""
        url = "https://example.com/file"
        mock_response = _make_mock_response(
            url=url,
            content_type="text/plain",
            cd_filename="../../etc/passwd",
            chunks=[b"data"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url=url,
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

        with pytest.raises(
            DownloadFileError, match="Network error: connection refused"
        ):
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

        url = "https://example.com/file"
        success_response = _make_mock_response(
            url=url,
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
                url=url,
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

    async def test_download_file_destination_with_filename(
        self, bot, tmp_dir, mock_session
    ):
        """Если destination содержит имя файла."""
        chunks = [b"chunk1", b"chunk2"]
        url = "https://example.com/remote.pdf"
        mock_response = _make_mock_response(
            url=url,
            content_type="application/pdf",
            cd_filename="server_name.pdf",  # Имя от сервера
            chunks=chunks,
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        # destination содержит своё имя файла
        filename = "my_custom_name.pdf"
        dist_with_filename = tmp_dir / filename
        result = await bot.download_file(
            url=url, destination=dist_with_filename, filename=filename
        )

        # Создастся папка с именем файла и внутри файл
        assert result == dist_with_filename / filename
        assert result.read_bytes() == b"".join(chunks)

        (dist_with_filename / filename).unlink()
        dist_with_filename.rmdir()

        # Теперь если файл существует, то будет ошибка
        dist_with_filename.write_text("test")
        with pytest.raises(FileExistsError):
            result = await bot.download_file(
                url=url, destination=dist_with_filename, filename=filename
            )

    async def test_download_file_destination_and_filename_collision(
        self, bot, tmp_dir, mock_session
    ):
        """Проверка коллизии имён когда destination содержит имя файла."""
        # Создаём существующий файл
        existing_file = tmp_dir / "report.pdf"
        existing_file.write_bytes(b"old content")

        chunks = [b"new content"]
        url = "https://example.com/file"
        mock_response = _make_mock_response(
            url=url,
            chunks=chunks,
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        # Пытаемся скачать в тот же путь
        result = await bot.download_file(
            url=url,
            destination=tmp_dir,
            filename="report.pdf",
        )

        # Должен быть создан новый файл с суффиксом (2)
        assert result == tmp_dir / "report(2).pdf"
        assert result.read_bytes() == b"".join(chunks)
        # Старый файл не должен быть перезаписан
        assert existing_file.read_bytes() == b"old content"

    async def test_download_file_destination_directory_uses_server_filename(
        self, bot, tmp_dir, mock_session
    ):
        """
        Проверка, что при указании директории используется имя от сервера.
        """
        chunks = [b"data"]
        url = "https://example.com/download"
        mock_response = _make_mock_response(
            url=url,
            content_type="text/plain",
            cd_filename="server_file.txt",
            chunks=chunks,
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        # destination - только директория (без имени файла)
        result = await bot.download_file(
            url=url,
            destination=tmp_dir,
        )

        # Должно использоваться имя от сервера
        assert result == tmp_dir / "server_file.txt"
        assert result.read_bytes() == b"".join(chunks)

    async def test_download_file__filename_with_path__dest_with_filename(
        self, bot, tmp_dir, mock_session
    ):
        """Проверка:
        - filename содержит путь
        - destination содержит имя файла
        """
        chunks = [b"binary"]
        url = "https://example.com/data"
        mock_response = _make_mock_response(
            url=url,
            cd_filename="data.bin",
            chunks=chunks,
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        destination = tmp_dir / "downloads"
        result = await bot.download_file(
            url=url,
            destination=destination,
            filename=destination / "filename.pdf",  # содержит путь
        )

        # Файл должен быть сохранён внутри директории с переданным именем
        assert result == destination / "filename.pdf"
        assert result.read_bytes() == b"".join(chunks)

        mock_response.closed = False
        result = await bot.download_file(
            url=url,
            destination=destination / "othername.jpg",  # содержит имя файла
            filename="filename.pdf",
        )

        # Файл должен быть сохранён внутри директории с переданным именем
        # FIXME провал:
        # Сохраняет в downloads/othername.jpg/filename.pdf
        assert result == destination / "filename.pdf"
        assert result.read_bytes() == b"".join(chunks)

    async def test_download_file_destination_relative_plus_filename(
        self, bot, tmp_dir, mock_session
    ):
        """Скачивание с относительным путём к файлу."""
        import os

        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_dir)

            chunks = [b"relative"]
            url = "https://example.com/file"
            mock_response = _make_mock_response(
                url=url,
                cd_filename="ignored.txt",
                chunks=chunks,
            )
            mock_session.request = AsyncMock(return_value=mock_response)

            # Относительный путь с расширением
            destination = "subdir"
            filename = "my_file.txt"
            result = await bot.download_file(
                url=url,
                destination=destination,
                filename=filename,
            )

            # Приводим оба пути к абсолютным для сравнения
            assert result.resolve() == (Path(destination) / filename).resolve()
            assert result.read_bytes() == b"".join(chunks)
            assert result.exists()
        finally:
            os.chdir(original_cwd)


class TestDownloadFileAsBytes:
    """
    Тесты для метода download_bytes.

    Примеры реальных URL для ручного тестирования:
    - Файл с подписью:
      https://fd.oneme.ru/getfile?sig=...&expires=...&clientType=3&id=...
    - Изображение:
      https://i.oneme.ru/i?r=BTGBPUwtwgYUeoFhO7rESmr81n-DnwjHYFhx5_EAhKk...
    """

    async def test_download_bytes_success(self, bot, mock_session):
        """
        Успешное скачивание файла в память.

        Эмулирует поведение реального эндпоинта типа:
        GET https://fd.oneme.ru/getfile?sig=...&expires=...
        """
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        mock_response = _make_mock_response(
            url=REAL_URL_LINKS["file"]["url"],
            content_type=REAL_URL_LINKS["file"]["content_type"],
            cd_filename=REAL_URL_LINKS["file"]["cd_filename"],
            chunks=chunks,
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_bytes(url=REAL_URL_LINKS["file"]["url"])

        assert result == b"chunk1chunk2chunk3"
        mock_response.release.assert_called_once()

    async def test_download_bytes_image_url(self, bot, mock_session):
        """
        Скачивание изображения с i.oneme.ru.
        """
        # Эмулируем PNG-изображение (минимальный валидный заголовок)
        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        mock_response = _make_mock_response(
            url=REAL_URL_LINKS["sticker"]["url"],
            content_type=REAL_URL_LINKS["sticker"]["content_type"],
            chunks=[png_header],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_bytes(url=REAL_URL_LINKS["sticker"]["url"])

        assert result.startswith(b"\x89PNG")
        assert len(result) > 0

    async def test_download_bytes_http_error(self, bot, mock_session):
        """DownloadFileError при HTTP 404."""
        mock_response = _make_mock_response(ok=False, status=404)
        mock_session.request = AsyncMock(return_value=mock_response)

        url = "https://example.com/missing"
        with pytest.raises(DownloadFileError, match="HTTP 404"):
            await bot.download_bytes(url=url)

    async def test_download_bytes_connection_error(self, bot, mock_session):
        """DownloadFileError при ошибке соединения."""
        from aiohttp import ClientConnectionError

        mock_session.request = AsyncMock(
            side_effect=ClientConnectionError("timeout")
        )
        bot.default_connection.max_retries = 0

        url = "https://example.com/file"
        with pytest.raises(DownloadFileError, match="Network error: timeout"):
            await bot.download_bytes(url=url)

    async def test_download_bytes_retry_on_503(self, bot, mock_session):
        """Retry при 503, затем успех."""
        retry_response = _make_mock_response(ok=False, status=503)
        retry_response.read = AsyncMock()

        url = "https://example.com/file"
        success_response = _make_mock_response(
            url=url,
            content_type="text/plain",
            chunks=[b"success"],
        )

        mock_session.request = AsyncMock(
            side_effect=[retry_response, success_response]
        )
        bot.default_connection.max_retries = 1
        bot.default_connection.retry_backoff_factor = 0.0

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await bot.download_bytes(url=url)
            assert result == b"success"

    async def test_download_bytes_empty_file(self, bot, mock_session):
        """Скачивание пустого файла."""
        url = "https://example.com/empty"
        mock_response = _make_mock_response(
            url=url,
            content_type="application/octet-stream",
            chunks=[],  # Пустой итератор
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_bytes(url=url)
        assert result == b""

    async def test_download_bytes_encoded_filename(self, bot, mock_session):
        """Скачивание пустого файла."""
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        url = (
            "https://fd.oneme.ru/getfile?sig=Dm00IcsNNg1fIU1X4CB_R0777"
            "_saII2AAtcffL6lmnT3TTiVuBBB95jo-4qfyGElLLh1w4ZdD4QpwliVoW77Kg"
            "&expires=1779148580110&clientType=3&id=3100094539&userId=111973341"
        )
        mock_response = _make_mock_response(
            url=url,
            cd_filename="%D0%94%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D0%BD%D1%82.pdf",
            content_type="application/octet-stream",
            chunks=chunks,
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_bytes(url=url)
        assert result == b"".join(chunks)

    async def test_download_file_vs_bytes_same_content(
        self, bot, tmp_dir, mock_session
    ):
        """
        download_file и download_bytes возвращают одинаковые данные
        """
        content = b"test content for comparison"
        chunks = [content[i : i + 10] for i in range(0, len(content), 10)]
        url = "https://example.com/file"

        # Для download_file
        mock_response_disk = _make_mock_response(
            url=url,
            cd_filename="test.txt",
            chunks=chunks.copy(),
        )
        # Для download_bytes
        mock_response_bytes = _make_mock_response(
            url=url,
            cd_filename="test.txt",
            chunks=chunks.copy(),
        )

        # Мокаем request дважды: первый вызов — для disk, второй — для bytes
        mock_session.request = AsyncMock(
            side_effect=[mock_response_disk, mock_response_bytes]
        )

        # Скачиваем на диск
        path = await bot.download_file(url=url, destination=tmp_dir)
        disk_content = path.read_bytes()

        # Скачиваем в память
        bio = await bot.download_bytes_io(url=url)
        bytes_content = bio.read()

        assert path.name == bio.name
        assert disk_content == bytes_content == content

    @freeze_datetime("maxapi.connection.base", datetime.now())
    async def test_download_file_name_collision(
        self, bot, tmp_dir, mock_session
    ):
        """Проверка, что при коллизии имён добавляется (2), (3) и т.д."""

        # Пытаемся скачать сразу 5 файлов
        results: list[Path] = []
        for i in range(5):
            url = f"https://i.oneme.ru/i?r=file{i + 1}"
            mock_response = _make_mock_response(
                url=url, chunks=[f"new {i + 1}".encode()]
            )
            mock_session.request = AsyncMock(return_value=mock_response)
            results.append(
                await bot.download_file(
                    url=url,
                    destination=tmp_dir,
                )
            )

        for i, result in enumerate(results):
            if i == 0:  # Первый файл не проверяем
                # Первый файл должен быть без суффикса _N
                # Только image_date_time
                assert "(" not in result.stem
                assert ")" not in result.stem
            else:
                # Ожидаем, что файлы сохранится с суффиксами
                assert result.stem.endswith(f"({i + 1})")
                assert result.read_bytes() == f"new {i + 1}".encode()

    async def test_download_file_image_correct_extension(
        self, bot, tmp_dir, mock_session
    ):
        """
        Для i.oneme.ru расширение определяется по Content-Type, а не .webp
        """
        mock_response = _make_mock_response(
            url=REAL_URL_LINKS["sticker"]["url"],
            content_type=REAL_URL_LINKS["sticker"]["content_type"],
            chunks=[b"\x89PNG\r\n\x1a\n"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_file(
            url=REAL_URL_LINKS["sticker"]["url"],
            destination=tmp_dir,
        )

        assert result.suffix == ".png"  # не .webp!
        assert result.name.startswith("sticker_")

    async def test_download_file_retryable_server_error(
        self, bot, mock_session
    ):
        """
        Покрытие ветки: except _RetryableServerError -> DownloadFileError
        """
        mock_response = _make_mock_response(status=502)
        mock_session.request = AsyncMock(return_value=mock_response)

        with pytest.raises(DownloadFileError) as exc_info:
            await bot.download_bytes(url="https://i.oneme.ru/i?r=test")

        assert "HTTP 502" in str(exc_info.value)

    @freeze_datetime("maxapi.connection.base", "2026-04-16 10:30:50")
    async def test_capture_filename_no_extension_fallback(self, bot):
        """Покрытие: is_image=True, ext='', fallback на .webp"""
        # 1. Случай с изображением
        url = "https://i.oneme.ru/"  # Нет имени файла в URL
        mock_response = _make_mock_response(
            url=url,
            content_type=None,  # type: ignore # Нет заголовка и content_type
        )

        filename = bot._capture_filename(mock_response)

        assert filename == "260416_103050.bin"

    def test_capture_filename_wrong_response(self, bot):
        """Покрытие: except (TypeError, AttributeError) при доступе к полям"""

        class BrokenResponse:
            pass

        with pytest.raises(TypeError, match="Ожидается ClientResponse"):
            bot._capture_filename(BrokenResponse())  # type: ignore

    @freeze_datetime("maxapi.connection.base", "2026-04-16 10:30:50")
    def test_capture_filename_minimal_object(self, bot):
        """Покрытие: except (TypeError, AttributeError) при доступе к полям"""
        # Нет ни content_disposition, ни url, ни content_type
        mock_response = _make_mock_response(
            content_type=None,  # type: ignore
        )

        filename = bot._capture_filename(mock_response)
        assert filename == "260416_103050.bin"  # fallback-результат


class FailingAsyncStream:
    """
    Имитирует async generator, который падает на первой итерации.
    Именно это вызывает срабатывание блока except Exception в download_file.
    """

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise RuntimeError("Ошибка сети при чтении потока")


class TestInternalUncoveredParts:
    async def test_fetch_content_stream_closed_response(self, bot):
        """Проверка ветки: response.closed == True"""
        mock_response = _make_mock_response(
            ok=True,
            closed=True,
        )

        with pytest.raises(
            DownloadFileError, match="response соединение закрыто"
        ):
            async for _ in bot._fetch_content_stream(mock_response):
                pass

        mock_response.release.assert_not_called()

    async def test_fetch_content_stream_http_error(self, bot):
        """Проверка ветки: response.ok == False"""
        mock_response = _make_mock_response(
            ok=False,
            closed=False,
            status=403,  # любой не-2xx статус
        )

        with pytest.raises(
            DownloadFileError, match="Ошибка при скачивании: HTTP 403"
        ):
            async for _ in bot._fetch_content_stream(mock_response):
                pass

        mock_response.release.assert_called_once()

    async def test_download_file_cleanup_partial_file_on_error(self, bot):
        """Проверка download_file ветки:
        except Exception:
            # При любой ошибке удаляем частично записанный файл
            if final_path.exists():
                final_path.unlink()
            raise
        """

        # Мокаем цепочку, чтобы дойти до try...except
        bot._fetch_response = AsyncMock()
        bot._fetch_response.return_value = Mock()
        bot._capture_filename = MagicMock(return_value="260416_103000.bin")

        # Файл уже частично создан
        # (например, записался первый чанк, потом ошибка)
        mock_final_path = MagicMock(spec=Path)
        mock_final_path.exists.return_value = True
        bot._check_file_exists = MagicMock(return_value=mock_final_path)

        # 3. Ломаем поток именно на этапе async for chunk in ...
        bot._fetch_content_stream = MagicMock(
            return_value=FailingAsyncStream()
        )

        # 4. Мокаем aiofiles.open как контекстный менеджер
        mock_file = AsyncMock()
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_file)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        # Важно: путь в patch должен совпадать с тем,
        # как aiofiles импортирован в вашем модуле
        with (
            patch("aiofiles.open", return_value=mock_cm),
            pytest.raises(RuntimeError, match="Ошибка сети при чтении потока"),
        ):
            await bot.download_file("http://example.com/file", "/tmp/dl")

        # ✅ 5. Проверяем покрытие целевой ветки
        mock_final_path.exists.assert_called_once()
        mock_final_path.unlink.assert_called_once()

    @freeze_datetime("maxapi.connection.base", "2026-04-16 10:30:50")
    async def test_download_image_broken_image_id(self, bot, mock_session):
        """
        Проверяем определение имени файла изображения в случае невозможности
        выделить уникальную часть токена изображения. Блок:
        def _get_image_id(r: str):
            ...
            try:
                data = base64.b64decode(r)
        """
        url_case = REAL_URL_LINKS["image"]
        mock_response = _make_mock_response(
            url=url_case["url"][:-30],  # отрезаем данные
            content_type=url_case["content_type"],
            chunks=[b"imagedata"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_bytes_io(url=url_case["url"])

        assert result.name != url_case["expected"]
        assert result.name == "image_260416_103050.webp"

        """
        Блок:
        def _get_image_id(r: str):
            ...
            if len(data) < 50:
                return None
        """
        mock_response.url = URL(url_case["url"][:-31])  # отрезаем данные
        mock_response.closed = False
        # mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_bytes_io(url=url_case["url"])

        assert result.name != url_case["expected"]
        assert result.name == "image_260416_103050.webp"

    @freeze_datetime("maxapi.connection.base", "2026-04-16 10:30:50")
    async def test_download_sticker_broken_id(self, bot, mock_session):
        """Скачивание вложения-аудио"""
        url_case = REAL_URL_LINKS["sticker"]
        mock_response = _make_mock_response(
            url="https://i.oneme.ru/getSmile?brokensmileId=None&smileType=4",
            cd_filename=url_case["cd_filename"],
            chunks=[b"PNGdata"],
        )
        mock_session.request = AsyncMock(return_value=mock_response)

        result = await bot.download_bytes_io(url=url_case["url"])

        assert result.name != url_case["expected"]
        assert result.name == "sticker_260416_103050.png"
