"""Тесты для методов download_file / download_bytes / download_bytes_io."""

from datetime import datetime
from functools import wraps
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from maxapi.bot import Bot
from maxapi.exceptions.download_file import DownloadFileError
from requests import ConnectionError

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
}


@pytest.fixture
def bot():
    return Bot(token="test-token")


@pytest.fixture
def tmp_dir(tmp_path: Path):
    return tmp_path


def _make_mock_response(
    *,
    ok=True,
    status_code=200,
    content_type="application/octet-stream",
    cd_filename=None,
    chunks=None,
    url=None,
):
    """Создаёт мок requests.Response для скачивания."""
    mock_response = MagicMock()
    mock_response.ok = ok
    mock_response.status_code = status_code
    mock_response.headers = {}

    if content_type is not None:
        mock_response.headers["Content-Type"] = content_type

    if cd_filename is not None:
        mock_response.headers["Content-Disposition"] = (
            f'attachment; filename="{cd_filename}"'
        )

    mock_response.url = url if url is not None else ""

    if chunks is not None:
        mock_response.iter_content = MagicMock(return_value=iter(chunks))

    return mock_response


@pytest.fixture
def mock_session(bot: Bot):
    """Создаёт мок-сессию и привязывает к боту."""
    session = MagicMock()
    session.closed = False
    bot.session = session
    return session


def freeze_datetime(
    target_module: str, fixed_dt: datetime | str, *, attr: str = "datetime"
):
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

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with patch(patch_target) as mock_dt:
                mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
                mock_dt.now.return_value = fixed_dt
                return func(*args, **kwargs)

        return wrapper

    return decorator


class TestDownloadFile:
    def test_download_file_path_as_str(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """Скачивание файла с корректным Content-Disposition."""
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        url_case = REAL_URL_LINKS["file"]

        mock_response = _make_mock_response(
            url=url_case["url"],
            chunks=chunks,
            cd_filename=url_case["cd_filename"],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_file(
            url=url_case["url"],
            destination=str(tmp_dir),
        )

        assert result == tmp_dir / url_case["expected"]
        assert result.read_bytes() == b"".join(chunks)

    def test_download_file_success(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """Скачивание файла с корректным Content-Disposition."""
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        url_case = REAL_URL_LINKS["file"]

        mock_response = _make_mock_response(
            url=url_case["url"],
            content_type=REAL_URL_LINKS["file"]["content_type"],
            cd_filename=url_case["cd_filename"],
            chunks=chunks,
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_file(
            url=url_case["url"],
            destination=tmp_dir,
        )

        assert result == tmp_dir / url_case["expected"]
        assert result.read_bytes() == b"".join(chunks)

    def test_download_file_no_content_disposition(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """Без Content-Disposition имя генерируется по MIME: file.ext."""
        url = "https://example.com/img"
        mock_response = _make_mock_response(
            url=url,
            content_type="image/jpeg",
            chunks=[b"imagedata"],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_file(url=url, destination=tmp_dir)
        assert result.name.startswith("file")
        assert result.parent == tmp_dir

    @freeze_datetime("maxapi.connection.base", "2026-04-16 10:30:50")
    def test_download_file_no_content_disposition_no_path(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """Без CD, без MIME, без внятного пути — fallback на datetime.bin."""
        url = "https://example.com/"
        mock_response = _make_mock_response(
            url=url,
            content_type=None,  # type: ignore
            chunks=[b"some_binary_data"],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_file(url=url, destination=tmp_dir)

        assert result.name == "260416_103050.bin"
        assert result.parent == tmp_dir

    def test_download_image(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """Скачивание вложения-изображения с i.oneme.ru."""
        url_case = REAL_URL_LINKS["image"]
        mock_response = _make_mock_response(
            url=url_case["url"],
            content_type=url_case["content_type"],
            chunks=[b"imagedata"],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_file(
            url=url_case["url"],
            destination=tmp_dir,
        )

        assert result.name == url_case["expected"]
        assert result.parent == tmp_dir

    def test_download_image_user_avatar(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """Скачивание аватара пользователя."""
        url_case = REAL_URL_LINKS["image_user_avatar"]
        mock_response = _make_mock_response(
            url=url_case["url"],
            content_type=url_case["content_type"],
            chunks=[b"imagedata"],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_file(
            url=url_case["url"],
            destination=tmp_dir,
        )

        assert result.name == url_case["expected"]
        assert result.parent == tmp_dir

    def test_download_video(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """Скачивание вложения-видео."""
        url_case = REAL_URL_LINKS["video"]
        mock_response = _make_mock_response(
            url=url_case["url"],
            cd_filename=url_case["cd_filename"],
            content_type=url_case["content_type"],
            chunks=[b"mp4videodata"],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_file(
            url=url_case["url"],
            destination=tmp_dir,
        )

        assert result.name == url_case["cd_filename"]
        assert result.parent == tmp_dir

    def test_download_audio(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """Скачивание вложения-аудио."""
        url_case = REAL_URL_LINKS["audio"]
        mock_response = _make_mock_response(
            url=url_case["url"],
            cd_filename=url_case["cd_filename"],
            content_type=url_case["content_type"],
            chunks=[b"mp3audiodata"],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_file(
            url=url_case["url"],
            destination=tmp_dir,
        )

        assert result.name == url_case["cd_filename"]
        assert result.parent == tmp_dir

    def test_download_sticker(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """Скачивание стикера с i.oneme.ru."""
        url_case = REAL_URL_LINKS["sticker"]
        mock_response = _make_mock_response(
            url=url_case["url"],
            cd_filename=url_case["cd_filename"],
            content_type=url_case["content_type"],
            chunks=[b"PNGdata"],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_file(
            url=url_case["url"],
            destination=tmp_dir,
        )

        assert result.name == url_case["expected"]
        assert result.parent == tmp_dir

    def test_download_file_path_traversal_protection(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """Защита от path traversal в filename."""
        url = "https://example.com/file"
        mock_response = _make_mock_response(
            url=url,
            content_type="text/plain",
            cd_filename="../../etc/passwd",
            chunks=[b"data"],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_file(url=url, destination=tmp_dir)

        assert result.parent == tmp_dir
        assert result.name == "passwd"

    def test_download_file_http_error(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """DownloadFileError при HTTP 404."""
        mock_response = _make_mock_response(ok=False, status_code=404)
        mock_session.get = MagicMock(return_value=mock_response)

        with pytest.raises(DownloadFileError, match="HTTP 404"):
            bot.download_file(
                url="https://example.com/missing",
                destination=tmp_dir,
            )

    def test_download_file_connection_error_raises(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
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
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """Retry при 503, затем успех."""
        retry_response = _make_mock_response(ok=False, status_code=503)

        url = "https://example.com/file"
        success_response = _make_mock_response(
            url=url,
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
            result = bot.download_file(url=url, destination=tmp_dir)

        assert result.name == "result.txt"

    def test_download_file_destination_with_filename(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """Если destination содержит имя файла, создаётся папка под него."""
        chunks = [b"chunk1", b"chunk2"]
        url = "https://example.com/remote.pdf"
        mock_response = _make_mock_response(
            url=url,
            content_type="application/pdf",
            cd_filename="server_name.pdf",
            chunks=chunks,
        )
        mock_session.get = MagicMock(return_value=mock_response)

        filename = "my_custom_name.pdf"
        dist_with_filename = tmp_dir / filename
        result = bot.download_file(
            url=url, destination=dist_with_filename, filename=filename
        )

        # Создастся папка с именем файла и внутри файл
        assert result == dist_with_filename / filename
        assert result.read_bytes() == b"".join(chunks)

        (dist_with_filename / filename).unlink()
        dist_with_filename.rmdir()

        # Если файл существует, то будет ошибка
        dist_with_filename.write_text("test")
        with pytest.raises(FileExistsError):
            bot.download_file(
                url=url, destination=dist_with_filename, filename=filename
            )

    def test_download_file_destination_and_filename_collision(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """Коллизия имён: добавляется суффикс (2)."""
        existing_file = tmp_dir / "report.pdf"
        existing_file.write_bytes(b"old content")

        chunks = [b"new content"]
        url = "https://example.com/file"
        mock_response = _make_mock_response(url=url, chunks=chunks)
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_file(
            url=url,
            destination=tmp_dir,
            filename="report.pdf",
        )

        assert result == tmp_dir / "report(2).pdf"
        assert result.read_bytes() == b"".join(chunks)
        assert existing_file.read_bytes() == b"old content"

    def test_download_file_destination_directory_uses_server_filename(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """При указании директории используется имя от сервера."""
        chunks = [b"data"]
        url = "https://example.com/download"
        mock_response = _make_mock_response(
            url=url,
            content_type="text/plain",
            cd_filename="server_file.txt",
            chunks=chunks,
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_file(url=url, destination=tmp_dir)

        assert result == tmp_dir / "server_file.txt"
        assert result.read_bytes() == b"".join(chunks)

    def test_download_file__filename_with_path__dest_with_filename(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """filename содержит путь + destination содержит имя файла."""
        chunks = [b"binary"]
        url = "https://example.com/data"

        def mock_response(*args, **kwargs):
            return _make_mock_response(
                url=url,
                cd_filename="data.bin",
                chunks=chunks,
            )

        mock_session.get = MagicMock(side_effect=mock_response)

        destination = tmp_dir / "downloads"
        result = bot.download_file(
            url=url,
            destination=destination,
            filename=destination / "filename.pdf",  # содержит путь
        )

        assert result == destination / "filename.pdf"
        assert result.read_bytes() == b"".join(chunks)

        result = bot.download_file(
            url=url,
            destination=destination / "othername.jpg",  # содержит имя файла
            filename="filename.pdf",
        )

        # Сохраняет в downloads/othername.jpg/filename.pdf
        assert result == destination / "othername.jpg" / "filename.pdf"
        assert result.read_bytes() == b"".join(chunks)

    def test_download_file_destination_relative_plus_filename(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
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
            mock_session.get = MagicMock(return_value=mock_response)

            destination = "subdir"
            filename = "my_file.txt"
            result = bot.download_file(
                url=url,
                destination=destination,
                filename=filename,
            )

            assert result.resolve() == (
                Path(destination) / filename
            ).resolve()
            assert result.read_bytes() == b"".join(chunks)
            assert result.exists()
        finally:
            os.chdir(original_cwd)


class TestDownloadFileAsBytes:
    """
    Тесты для методов download_bytes / download_bytes_io.

    Примеры реальных URL для ручного тестирования:
    - Файл с подписью:
      https://fd.oneme.ru/getfile?sig=...&expires=...&clientType=3&id=...
    - Изображение:
      https://i.oneme.ru/i?r=BTGBPUwtwgYUeoFhO7rESmr81n-DnwjHYFhx5_EAhKk...
    """

    def test_download_bytes_success(
        self, bot: Bot, mock_session: MagicMock
    ):
        """Успешное скачивание файла в память."""
        chunks = [b"chunk1", b"chunk2", b"chunk3"]
        mock_response = _make_mock_response(
            url=REAL_URL_LINKS["file"]["url"],
            content_type=REAL_URL_LINKS["file"]["content_type"],
            cd_filename=REAL_URL_LINKS["file"]["cd_filename"],
            chunks=chunks,
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_bytes(url=REAL_URL_LINKS["file"]["url"])

        assert result == b"chunk1chunk2chunk3"

    def test_download_bytes_image_url(
        self, bot: Bot, mock_session: MagicMock
    ):
        """Скачивание изображения с i.oneme.ru."""
        png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        mock_response = _make_mock_response(
            url=REAL_URL_LINKS["sticker"]["url"],
            content_type=REAL_URL_LINKS["sticker"]["content_type"],
            chunks=[png_header],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_bytes(url=REAL_URL_LINKS["sticker"]["url"])

        assert result.startswith(b"\x89PNG")
        assert len(result) > 0

    def test_download_bytes_http_error(
        self, bot: Bot, mock_session: MagicMock
    ):
        """DownloadFileError при HTTP 404."""
        mock_response = _make_mock_response(ok=False, status_code=404)
        mock_session.get = MagicMock(return_value=mock_response)

        url = "https://example.com/missing"
        with pytest.raises(DownloadFileError, match="HTTP 404"):
            bot.download_bytes(url=url)

    def test_download_bytes_connection_error(
        self, bot: Bot, mock_session: MagicMock
    ):
        """DownloadFileError при ошибке соединения."""
        mock_session.get = MagicMock(
            side_effect=ConnectionError("timeout")
        )
        bot.default_connection.max_retries = 0

        url = "https://example.com/file"
        with pytest.raises(DownloadFileError, match="Ошибка при скачивании"):
            bot.download_bytes(url=url)

    def test_download_bytes_retry_on_503(
        self, bot: Bot, mock_session: MagicMock
    ):
        """Retry при 503, затем успех."""
        retry_response = _make_mock_response(ok=False, status_code=503)

        url = "https://example.com/file"
        success_response = _make_mock_response(
            url=url,
            content_type="text/plain",
            chunks=[b"success"],
        )

        mock_session.get = MagicMock(
            side_effect=[retry_response, success_response]
        )
        bot.default_connection.max_retries = 1
        bot.default_connection.retry_backoff_factor = 0.0

        with patch("time.sleep"):
            result = bot.download_bytes(url=url)
            assert result == b"success"

    def test_download_bytes_empty_file(
        self, bot: Bot, mock_session: MagicMock
    ):
        """Скачивание пустого файла."""
        url = "https://example.com/empty"
        mock_response = _make_mock_response(
            url=url,
            content_type="application/octet-stream",
            chunks=[],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_bytes(url=url)
        assert result == b""

    def test_download_bytes_encoded_filename(
        self, bot: Bot, mock_session: MagicMock
    ):
        """Скачивание с URL-encoded именем в Content-Disposition."""
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
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_bytes(url=url)
        assert result == b"".join(chunks)

    def test_download_file_vs_bytes_same_content(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """download_file и download_bytes возвращают одинаковые данные."""
        content = b"test content for comparison"
        chunks = [content[i : i + 10] for i in range(0, len(content), 10)]
        url = "https://example.com/file"

        mock_response_disk = _make_mock_response(
            url=url,
            cd_filename="test.txt",
            chunks=chunks.copy(),
        )
        mock_response_bytes = _make_mock_response(
            url=url,
            cd_filename="test.txt",
            chunks=chunks.copy(),
        )

        mock_session.get = MagicMock(
            side_effect=[mock_response_disk, mock_response_bytes]
        )

        path = bot.download_file(url=url, destination=tmp_dir)
        disk_content = path.read_bytes()

        bio = bot.download_bytes_io(url=url)
        bytes_content = bio.read()

        assert path.name == bio.name
        assert disk_content == bytes_content == content

    @freeze_datetime("maxapi.connection.base", datetime.now())
    def test_download_file_name_collision(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """При коллизии имён добавляется (2), (3) и т.д."""
        results: list[Path] = []
        for i in range(5):
            url = f"https://i.oneme.ru/i?r=file{i + 1}"
            mock_response = _make_mock_response(
                url=url, chunks=[f"new {i + 1}".encode()]
            )
            mock_session.get = MagicMock(return_value=mock_response)
            results.append(
                bot.download_file(
                    url=url,
                    destination=tmp_dir,
                )
            )

        for i, result in enumerate(results):
            if i == 0:
                assert "(" not in result.stem
                assert ")" not in result.stem
            else:
                assert result.stem.endswith(f"({i + 1})")
                assert result.read_bytes() == f"new {i + 1}".encode()

    def test_download_file_image_correct_extension(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """Для i.oneme.ru расширение определяется по Content-Type, не .webp."""
        mock_response = _make_mock_response(
            url=REAL_URL_LINKS["sticker"]["url"],
            content_type=REAL_URL_LINKS["sticker"]["content_type"],
            chunks=[b"\x89PNG\r\n\x1a\n"],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_file(
            url=REAL_URL_LINKS["sticker"]["url"],
            destination=tmp_dir,
        )

        assert result.suffix == ".png"
        assert result.name.startswith("sticker_")

    def test_download_file_retryable_server_error(
        self, bot: Bot, mock_session: MagicMock
    ):
        """_RetryableServerError исчерпан -> DownloadFileError."""
        mock_response = _make_mock_response(status_code=502)
        mock_session.get = MagicMock(return_value=mock_response)

        with pytest.raises(DownloadFileError) as exc_info:
            bot.download_bytes(url="https://i.oneme.ru/i?r=test")

        assert "HTTP 502" in str(exc_info.value)

    @freeze_datetime("maxapi.connection.base", "2026-04-16 10:30:50")
    def test_capture_filename_no_extension_fallback(self, bot: Bot):
        """i.oneme.ru host, но путь пустой -> datetime.bin."""
        url = "https://i.oneme.ru/"
        mock_response = _make_mock_response(
            url=url,
            content_type=None,  # type: ignore
        )

        filename = bot._capture_filename(mock_response)

        assert filename == "260416_103050.bin"

    @freeze_datetime("maxapi.connection.base", "2026-04-16 10:30:50")
    def test_capture_filename_minimal_object(self, bot: Bot):
        """Нет ни CD, ни URL, ни content_type -> datetime.bin."""
        mock_response = _make_mock_response(
            content_type=None,  # type: ignore
        )

        filename = bot._capture_filename(mock_response)
        assert filename == "260416_103050.bin"


class TestInternalUncoveredParts:
    def test_fetch_content_stream_http_error(self, bot: Bot):
        """_fetch_content_stream проверяет response.ok."""
        mock_response = _make_mock_response(
            ok=False,
            status_code=403,
        )

        with pytest.raises(
            DownloadFileError, match="Ошибка при скачивании: HTTP 403"
        ):
            for _ in bot._fetch_content_stream(mock_response):
                pass

    def test_download_file_cleanup_partial_file_on_error(
        self, bot: Bot, tmp_dir: Path, mock_session: MagicMock
    ):
        """При ошибке во время записи частично записанный файл удаляется."""

        def failing_stream(*args, **kwargs):
            yield b"partial"
            raise RuntimeError("Ошибка сети при чтении потока")

        mock_response = _make_mock_response(
            url="https://example.com/file",
            cd_filename="partial.bin",
            chunks=[b"unused"],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        with (
            patch.object(
                bot,
                "_fetch_content_stream",
                return_value=failing_stream(),
            ),
            pytest.raises(RuntimeError, match="Ошибка сети при чтении потока"),
        ):
            bot.download_file(
                url="https://example.com/file",
                destination=tmp_dir,
            )

        assert not (tmp_dir / "partial.bin").exists()

    @freeze_datetime("maxapi.connection.base", "2026-04-16 10:30:50")
    def test_download_image_broken_image_id(
        self, bot: Bot, mock_session: MagicMock
    ):
        """Короткий r-параметр -> image_id None -> fallback на datetime."""
        url_case = REAL_URL_LINKS["image"]
        # Отрезаем данные, чтобы _get_image_id вернул None.
        mock_response = _make_mock_response(
            url=url_case["url"][:-30],
            content_type=url_case["content_type"],
            chunks=[b"imagedata"],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_bytes_io(url=url_case["url"])

        assert result.name != url_case["expected"]
        assert result.name == "image_260416_103050.webp"

    @freeze_datetime("maxapi.connection.base", "2026-04-16 10:30:50")
    def test_download_sticker_broken_id(
        self, bot: Bot, mock_session: MagicMock
    ):
        """Стикер без smileId -> fallback на datetime."""
        mock_response = _make_mock_response(
            url="https://i.oneme.ru/getSmile?brokensmileId=None&smileType=4",
            cd_filename=None,
            content_type="image/png",
            chunks=[b"PNGdata"],
        )
        mock_session.get = MagicMock(return_value=mock_response)

        result = bot.download_bytes_io(url=REAL_URL_LINKS["sticker"]["url"])

        assert result.name == "sticker_260416_103050.png"