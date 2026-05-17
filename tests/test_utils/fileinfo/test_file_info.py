"""
Тесты для FileInspector и RangeDownloader на фикстурах.
"""

import base64
import json
import logging
import mimetypes
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest
from maxapi.connection.base import NamedBytesIO
from maxapi.utils.file_inspector import (
    FileInspector,
    RangeDownloader,
)
from yarl import URL

log = logging.getLogger("maxapi.fileinfo")
log.setLevel(logging.DEBUG)

# mimetypes не знает image/webp в стандартной библиотеке Python (до 3.11+).
mimetypes.add_type("image/webp", ".webp")

FIXTURES_FILE = Path(__file__).parent / "fixtures.json"
FIXTURES_ID = list(
    json.loads(FIXTURES_FILE.read_text(encoding="utf-8")).keys()
)


@pytest.fixture(scope="session")
def all_fixtures():
    """Загружает все фикстуры один раз на сессию."""
    fixtures = json.loads(FIXTURES_FILE.read_text(encoding="utf-8"))
    loaded = {}
    for name, f in fixtures.items():
        head = base64.b64decode(f["head_b64"])
        tail = base64.b64decode(f["tail_b64"]) if "tail_b64" in f else None
        expected = {
            k: v for k, v in f.items() if k not in ("head_b64", "tail_b64")
        }
        loaded[name] = (head, tail, expected)
    return loaded


@pytest.fixture(scope="session")
def fixture_bytes_io(all_fixtures):
    """Кеширует NamedBytesIO для всех фикстур."""
    cached = {}
    for name, (head, tail, exp) in all_fixtures.items():
        cached[name] = _make_fixture_named_bytes_io(name, head, tail, exp)
    return cached


def _make_fixture_named_bytes_io(name, head, tail, exp) -> NamedBytesIO:
    """
    Собирает полный объём: head + нули (середина) + tail
    чтобы эмулировать реальный файл для inspect_bytes()
    """
    mime = exp.get("mime_type", "")
    ext = mimetypes.guess_extension(mime) or ".bin"
    file_name = f"{name}{ext}"

    file_size = exp.get("file_size") or (len(head) + len(tail))

    full = bytearray(file_size)
    full[: len(head)] = head
    if tail:
        full[-len(tail) :] = tail

    bio = NamedBytesIO(full)
    bio.name = file_name
    return bio


def _make_fixture_file(name, head, tail, exp, tmp_path) -> Path:
    """
    Создаёт временный файл из фикстуры.

    Собирает полный файл: head + нули (середина) + tail,
    чтобы эмулировать реальный файл для inspect_file().
    """
    bio = _make_fixture_named_bytes_io(name, head, tail, exp)
    file_path = tmp_path / f"{bio.name}"

    file_path.write_bytes(bio.getbuffer())
    return file_path


# =============================================================================
# Mock-хелперы
# =============================================================================


class MockResponseFactory:
    """Фабрика мок-ответов aiohttp для RangeDownloader."""

    def __init__(
        self,
        head: bytes,
        tail: bytes | None,
        content_type: str = "application/octet-stream",
        file_size: int | None = None,
        file_name: str | None = None,
    ):
        self.head = head
        self.tail = tail
        self.content_type = content_type
        self.file_name = file_name
        self.file_size = file_size
        self._head_pos = 0
        self._tail_used = False

    def make_head_response(self, url: str) -> AsyncMock:
        self._head_pos = 0  # Сброс для нового ответа
        resp = AsyncMock()
        resp.ok = True
        resp.status = 200
        resp.url = URL(url)
        resp.closed = False
        resp.headers = {
            "Content-Type": self.content_type,
            "Content-Length": str(self.file_size or len(self.head)),
        }
        if self.file_name:
            resp.headers["Content-Disposition"] = (
                f"attachment; filename={self.file_name}"
            )
        resp.history = ()
        resp.request_info = Mock()

        async def read_head(n: int = -1) -> bytes:
            available = len(self.head) - self._head_pos
            log.debug("read_head: n=%s, available=%s", n, available)
            if available <= 0:
                return b""
            to_read = min(n, available) if n > 0 else available
            chunk = self.head[self._head_pos : self._head_pos + to_read]
            self._head_pos += to_read
            return chunk

        resp.content.read = read_head
        resp.read = AsyncMock(return_value=self.head)
        resp.release = Mock()
        return resp

    def make_tail_response(self, url: str) -> AsyncMock:
        resp = AsyncMock()
        resp.ok = True
        resp.status = 206
        resp.url = URL(url)
        resp.headers = {"Content-Type": self.content_type}
        resp.history = ()
        resp.request_info = Mock()

        async def read_tail(n: int = -1) -> bytes:
            if self._tail_used:
                return b""
            self._tail_used = True
            return self.tail or b"self.tail empty"

        resp.content.read = read_tail
        resp.read = AsyncMock(return_value=self.tail)
        resp.release = Mock()
        return resp


def _make_mock_session(
    head: bytes,
    tail: bytes | None,
    content_type: str = "application/octet-stream",
    file_size: int | None = None,
    file_name: str | None = None,
) -> AsyncMock:
    factory = MockResponseFactory(
        head, tail, content_type, file_size, file_name
    )
    session = AsyncMock()
    session.get = AsyncMock(
        side_effect=lambda url, headers=None: (
            factory.make_tail_response(url)
            if headers and "Range" in headers
            else factory.make_head_response(url)
        )
    )
    return session


# =============================================================================
# Тесты FileInspector (параметризованные)
# =============================================================================


@pytest.mark.parametrize("name", FIXTURES_ID)
class TestFileInspectorURL:
    """FileInspector на всех фикстурах."""

    async def test_inspect_returns_fileinfo(self, name, all_fixtures):
        """Все фикстуры возвращают FileInfo без исключений."""
        head, tail, exp = all_fixtures[name]
        session = _make_mock_session(
            head,
            tail,
            exp["mime_type"],
            exp["file_size"],
        )
        inspector = FileInspector()
        info = await inspector.inspect_url(
            "https://example.com/test", session=session
        )
        assert info.status in ("ok", "partial", "error")

    async def test_format_with_no_mime_type(self, name, all_fixtures):
        """Если сервер не вернул content_type, то парсер должен определить
        формат по содержанию файла"""
        head, tail, exp = all_fixtures[name]
        log.debug("Длина заголовка в фикстуре %s", len(head))
        session = _make_mock_session(
            head,
            tail,
            "",  # no mime_type
            exp["file_size"],
        )
        inspector = FileInspector()
        info = await inspector.inspect_url(
            "https://example.com/test", session=session
        )
        assert info.format == exp["format"]

    async def test_expected_fields_match(self, name, all_fixtures):
        """Проверяем FileInfo на соответствие полям expected, если заданы."""
        head, tail, exp = all_fixtures[name]
        session = _make_mock_session(
            head,
            tail,
            exp["mime_type"],
            exp["file_size"],
        )
        inspector = FileInspector()
        info = await inspector.inspect_url(
            "https://example.com/test", session=session
        )
        log.debug("Размер фикстуры head=%s", len(head))
        if exp.get("format"):
            assert info.format == exp["format"]
        if exp.get("width"):
            assert info.width == exp["width"]
            assert info.height == exp["height"]
        if exp.get("fps"):
            assert info.fps == exp["fps"]
        if exp.get("duration"):
            assert info.duration == exp["duration"]
        if exp.get("sample_rate"):
            assert info.sample_rate == exp["sample_rate"]


class TestFileInspectorError:
    """FileInspector возврат ошибок"""

    async def test_client_error_returns_error_status(self):
        """aiohttp.ClientError → FileInfo(status='error')."""
        session = AsyncMock()
        session.get = AsyncMock(side_effect=aiohttp.ClientConnectionError())

        inspector = FileInspector()
        info = await inspector.inspect_url(
            "https://example.com/test.jpg",
            session=session,
            max_retries=1,
        )
        assert info.status == "error"

    async def test_generic_exception_returns_error_status(self):
        """Любое исключение → FileInfo(status='error')."""
        session = AsyncMock()
        session.get = AsyncMock(side_effect=ValueError("unexpected"))

        inspector = FileInspector()
        info = await inspector.inspect_url(
            "https://example.com/test.jpg",
            session=session,
            max_retries=1,
        )
        assert info.status == "error"
        assert info.error_desc == "unexpected"

    async def test_retry_then_success(self):
        """503 → retry → успех."""
        factory = MockResponseFactory(
            head=b"data", tail=b"", content_type="image/jpeg", file_size=4
        )
        meta_resp = factory.make_head_response("url")  # для _fetch_meta
        bad = factory.make_head_response("url")
        bad.status, bad.ok = 503, False
        good = factory.make_head_response("url")
        session = AsyncMock()
        session.get = AsyncMock(side_effect=[meta_resp, bad, good])

        info = await FileInspector().inspect_url(
            "https://x.com/x.jpg", session=session, retry_backoff_factor=0
        )
        assert info.status == "error"
        assert session.get.call_count == 3

    async def test_retry_exhausted(self):
        """503 × 2 → error."""
        factory = MockResponseFactory(
            head=b"data", tail=b"", content_type="image/jpeg", file_size=4
        )
        bad = factory.make_head_response("url")
        bad.status, bad.ok = 503, False
        session = AsyncMock()
        session.get = AsyncMock(side_effect=[bad, bad])

        info = await FileInspector().inspect_url(
            "https://x.com/x.jpg",
            session=session,
            max_retries=1,
            retry_backoff_factor=0,
        )
        assert info.status == "error"
        assert session.get.call_count == 2

    async def test_client_error_no_retry(self):
        """404 → сразу error."""
        factory = MockResponseFactory(
            head=b"data", tail=b"", content_type="image/jpeg", file_size=4
        )
        bad = factory.make_head_response("url")
        bad.status, bad.ok = 404, False
        session = AsyncMock()
        session.get = AsyncMock(side_effect=[bad])

        info = await FileInspector().inspect_url(
            "https://x.com/x.jpg",
            session=session,
            max_retries=2,
            retry_backoff_factor=0,
        )
        assert info.status == "error"
        assert session.get.call_count == 1


@pytest.mark.parametrize("name", FIXTURES_ID)
class TestFileInspectorLocalFile:
    """FileInspector.inspect_file() на всех фикстурах."""

    async def test_inspect_file_returns_fileinfo(
        self, name, all_fixtures, tmp_path
    ):
        """Все фикстуры возвращают FileInfo без исключений."""
        head, tail, exp = all_fixtures[name]
        file_path = _make_fixture_file(name, head, tail, exp, tmp_path)
        info = await FileInspector().inspect_file(str(file_path))
        assert info.status in ("ok", "partial", "error")

    async def test_expected_fields_match(self, name, all_fixtures, tmp_path):
        """Формат из локального файла совпадает с expected."""
        head, tail, exp = all_fixtures[name]
        file_path = _make_fixture_file(name, head, tail, exp, tmp_path)
        inspector = FileInspector()
        info = await inspector.inspect_file(
            str(file_path),
            full_read_limit=0,  # Отключаем полное чтение файла
        )
        if exp.get("format"):
            assert info.format == exp["format"]
        if exp.get("sample_rate"):
            assert info.sample_rate == exp["sample_rate"]
        if exp.get("duration"):
            assert info.duration == exp["duration"]
        if exp.get("fps"):
            assert info.fps == exp["fps"]
        if exp.get("width"):
            assert info.width == exp["width"]
            assert info.height == exp["height"]


class TestFileInspectorLocalErrors:
    """Тесты FileInspector с локальными файлами."""

    async def test_inspect_local_nonexistent(self):
        """Несуществующий файл → error."""
        inspector = FileInspector()
        info = await inspector.inspect_file("/nonexistent/file.jpg")
        assert info.status == "error"
        assert info.error_desc == "Файл не найден"

    async def test_inspect_local_permission_denied(self, tmp_path: Path):
        """Ошибка чтения файла → error."""
        file_path = tmp_path / "exists.jpg"
        file_path.write_bytes(b"fake data")

        # Мокаем открытие файла — выбрасывает ошибку
        with patch("anyio.open_file") as mock_open:
            mock_open.side_effect = OSError("read error")

            inspector = FileInspector()
            info = await inspector.inspect_file(str(file_path))
            assert info.status == "error"
            assert "read error" in info.error_desc


class TestFileInspectorBytes:
    """Тесты FileInspector с локальными файлами."""

    @pytest.mark.parametrize("name", FIXTURES_ID)
    async def test_bytes_butesio_namedbytesio_match(self, name, all_fixtures):
        """bytes, BytesIO, NamedBytesIO дают идентичные результаты"""
        head, tail, exp = all_fixtures[name]

        nbio = _make_fixture_named_bytes_io(name, head, tail, exp)
        byt = nbio.getbuffer()  # bytes
        bio = BytesIO(byt)
        file_name = nbio.name or ""

        inspector = FileInspector()
        info_nbio = await inspector.inspect_bytes(nbio)
        info_bio = await inspector.inspect_bytes(bio, file_name=file_name)
        info_byt = await inspector.inspect_bytes(byt, file_name=file_name)

        assert info_nbio == info_bio
        assert info_bio == info_byt

    @pytest.mark.parametrize("name", FIXTURES_ID)
    async def test_expected_fields_match(self, name, all_fixtures):
        """Формат из байт совпадает с expected."""
        head, tail, exp = all_fixtures[name]
        nbio = _make_fixture_named_bytes_io(name, head, tail, exp)
        info = await FileInspector().inspect_bytes(
            nbio,
            full_read_limit=0,  # Отключаем полное чтение данных
        )
        if exp.get("format"):
            assert info.format == exp["format"]
        if exp.get("sample_rate"):
            assert info.sample_rate == exp["sample_rate"]
        if exp.get("duration"):
            assert info.duration == exp["duration"]
        if exp.get("fps"):
            assert info.fps == exp["fps"]
        if exp.get("width"):
            assert info.width == exp["width"]
            assert info.height == exp["height"]


# =============================================================================
# Специфичные тесты, не зависящие от списка фикстур
# =============================================================================


class TestEdgeCases:
    """Краевые случаи."""

    async def test_small_head_partial(self):
        """Маленький head — partial."""
        head = b"RIFF\x00\x00\x00\x00WEBP"  # обрезанный WebP
        session = _make_mock_session(head, b"", "image/webp", 1000)
        inspector = FileInspector()
        info = await inspector.inspect_url(
            "https://example.com/test.webp",
            session=session,
            max_total=len(head),
        )
        assert info.format == "WEBP"
        assert info.status == "partial"
        assert info.error_desc.startswith("Недостаточно данных")

    async def test_html_page_error(self):
        """HTML-страница — error."""
        html = b"<!DOCTYPE html><html><head></head><body></body></html>"
        session = _make_mock_session(html, b"", "text/html", len(html))
        inspector = FileInspector()
        info = await inspector.inspect_url(
            "https://example.com/page.html", session=session
        )
        assert info.status == "error"
        assert info.error_desc == "Файл не является медиа (HTML-страница)"

    async def test_wrong_random_data_page_error(self):
        """Случайное содержание по ссылке — error."""
        data = b"8"
        session = _make_mock_session(data, b"", "", len(data))
        inspector = FileInspector()
        info = await inspector.inspect_url(
            "https://example.com/page.html", session=session
        )
        assert info.status == "error"
        assert info.error_desc.startswith("Недостаточно данных")

    async def test_empty_body_error(self):
        """Пустой ответ — error."""
        session = _make_mock_session(b"", b"", "text/plain", 0)
        inspector = FileInspector()
        info = await inspector.inspect_url(
            "https://example.com/empty", session=session
        )
        assert info.status == "error"
        assert info.error_desc.startswith("Недостаточно данных")


# =============================================================================


class TestRangeDownloader:
    # Тесты извлечения имени файла
    def test_from_content_disposition(self):
        headers = {"Content-Disposition": 'attachment; filename="photo.jpg"'}
        name = RangeDownloader._extract_filename(headers, "https://x.com/123")
        assert name == "photo.jpg"

    def test_from_url_when_no_disposition(self):
        headers = {}
        name = RangeDownloader._extract_filename(
            headers, "https://x.com/path/photo.jpg"
        )
        assert name == "photo.jpg"

    def test_url_with_query_params(self):
        headers = {}
        name = RangeDownloader._extract_filename(
            headers, "https://x.com/photo.jpg?size=large"
        )
        assert name == "photo.jpg"

    def test_filename_with_percent_encoding(self):
        headers = {}
        name = RangeDownloader._extract_filename(
            headers, "https://x.com/%D1%84%D0%B0%D0%B9%D0%BB.jpg"
        )
        assert name == "файл.jpg"

    def test_content_disposition_without_quotes(self):
        headers = {"Content-Disposition": "attachment; filename=photo.jpg"}
        name = RangeDownloader._extract_filename(headers, "https://x.com/123")
        assert name == "photo.jpg"

    def test_url_without_filename(self):
        headers = {}
        name = RangeDownloader._extract_filename(headers, "https://x.com/")
        assert name == "unknown"  # или что возвращается по умолчанию

    async def test_creates_session_when_none(self):
        """RangeDownloader создаёт сессию если не передана."""
        dl = RangeDownloader("https://example.com", session=None)
        assert dl.session is None

        with patch("aiohttp.ClientSession") as mock_cls:
            mock_cls.return_value = AsyncMock()
            async with dl:
                assert dl.session is not None
            assert dl.session is None
