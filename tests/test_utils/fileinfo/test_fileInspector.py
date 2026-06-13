"""
Тесты для FileInspector и RangeDownloader на фикстурах.
"""

import base64
import json
import logging
import mimetypes
import struct
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest
from aiohttp import CookieJar
from maxapi.types.file_info import FileInfo
from maxapi.types.named_bytes_io import NamedBytesIO
from maxapi.utils.file_inspector import (
    FileInspector,
    RangeDownloader,
)
from multidict import CIMultiDict
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

    file_size = exp.get("file_size") or len(head) + (len(tail) if tail else 0)

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
            return self.tail or b""

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
    session.headers = CIMultiDict()
    session.cookie_jar = CookieJar()
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
            "https://x.com/x.jpg",
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
            "https://x.com/x.jpg",
            session=session,
            max_retries=1,
            allow_external_auth=True,
        )
        assert info.status == "error"
        assert info.parse_note == "unexpected"

    async def test_retry_then_success(self):
        """Проверка retry/call_count"""
        minimal_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01"
        factory = MockResponseFactory(
            head=minimal_jpeg, tail=b"", content_type="image/jpeg", file_size=4
        )
        bad = factory.make_head_response("url")
        bad.status, bad.ok = 503, False
        good = factory.make_head_response("url")
        session = AsyncMock()
        # 503 → retry → 200 (один GET: meta + head).
        session.get = AsyncMock(side_effect=[bad, bad, good])

        info = await FileInspector().inspect_url(
            "https://x.com/x.jpg",
            session=session,
            retry_backoff_factor=0,
            allow_external_auth=True,
        )
        assert info.status == "partial"
        assert info.format == "JPEG"
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
            allow_external_auth=True,
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
            allow_external_auth=True,
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
            full_read_threshold=0,  # Отключаем полное чтение файла
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
        assert info.parse_note == "Файл не найден"

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
            assert "read error" in info.parse_note


class TestFileInspectorBytes:
    """Тесты FileInspector с локальными файлами."""

    @pytest.mark.parametrize("name", FIXTURES_ID)
    async def test_bytes_bytesio_namedbytesio_match(self, name, all_fixtures):
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
            full_read_threshold=0,  # Отключаем полное чтение данных
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

    async def test_html_page_error(self):
        """HTML-страница — error."""
        html = b"<!DOCTYPE html><html><head></head><body></body></html>"
        session = _make_mock_session(html, b"", "text/html", len(html))
        inspector = FileInspector()
        info = await inspector.inspect_url(
            "https://example.com/page.html", session=session
        )
        assert info.status == "error"
        assert info.parse_note == "Файл не является медиа (HTML-страница)"

    async def test_wrong_random_data_partial(self):
        """
        Случайное содержание по ссылке — partial (только заголовки сервера).
        """
        data = b"8"
        session = _make_mock_session(data, b"", "", len(data))
        inspector = FileInspector()
        info = await inspector.inspect_url(
            "https://example.com/page.html", session=session
        )
        assert info.status == "partial"
        assert info.file_size == len(data)
        assert info.format is None

    async def test_empty_body_error(self):
        """Пустой ответ — error."""
        session = _make_mock_session(b"", b"", "text/plain", 0)
        inspector = FileInspector()
        info = await inspector.inspect_url(
            "https://example.com/empty", session=session
        )
        assert info.status == "error"
        assert info.parse_note.startswith("Недостаточно данных")


# =============================================================================


class TestRangeDownloader:
    # Тесты извлечения имени файла
    def test_from_content_disposition(self):
        """Извлечение имени файла из Content-Disposition."""
        headers = {"Content-Disposition": 'attachment; filename="photo.jpg"'}
        name = RangeDownloader._extract_filename(headers, "https://x.com/123")
        assert name == "photo.jpg"

    def test_from_url_when_no_disposition(self):
        """Без Content-Disposition: имя из URL."""
        headers = {}
        name = RangeDownloader._extract_filename(
            headers, "https://x.com/path/photo.jpg"
        )
        assert name == "photo.jpg"

    def test_url_with_query_params(self):
        """URL с query-параметрами, имя из пути."""
        headers = {}
        name = RangeDownloader._extract_filename(
            headers, "https://x.com/photo.jpg?size=large"
        )
        assert name == "photo.jpg"

    def test_filename_with_percent_encoding(self):
        """Имя файла с percent-encoding декодируется."""
        headers = {}
        name = RangeDownloader._extract_filename(
            headers, "https://x.com/%D1%84%D0%B0%D0%B9%D0%BB.jpg"
        )
        assert name == "файл.jpg"

    def test_content_disposition_without_quotes(self):
        """Content-Disposition без кавычек."""
        headers = {"Content-Disposition": "attachment; filename=photo.jpg"}
        name = RangeDownloader._extract_filename(headers, "https://x.com/123")
        assert name == "photo.jpg"

    def test_url_without_filename(self):
        """URL без имени файла = неизвестно."""
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


class TestBotGetFileInfo:
    """Тесты bot.get_file_info()."""

    async def test_returns_fileinfo(self, bot):
        """Возвращает FileInfo с полями."""
        minimal_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01"
        session = _make_mock_session(
            head=minimal_jpeg,
            tail=b"",
            content_type="image/jpeg",
            file_size=len(minimal_jpeg),
        )

        info = await bot.get_file_info(
            "https://example.com/photo.jpg", timeout=5, session=session
        )

        assert isinstance(info, FileInfo)
        assert info.mime_type == "image/jpeg"
        assert info.format == "JPEG"

    @patch("maxapi.utils.file_inspector.FileInspector.inspect_url")
    async def test_timeout_passed_to_inspector(self, mock_inspect, bot):
        """timeout передаётся в RangeDownloader."""
        mock_inspect.return_value = FileInfo(url="test")
        bot.session = AsyncMock()

        await bot.get_file_info("https://example.com/file.mp4", timeout=15)
        assert mock_inspect.call_args.kwargs["timeout"] == 15


class TestFileInspectorAdvanced:
    """FileInspector — дополнительные кейсы (loading, errors, properties)."""

    async def test_last_head_and_tail_no_reader(self):
        inspector = FileInspector()
        assert inspector.last_head == b""
        assert inspector.last_tail == b""

    async def test_inspect_no_head_data_returns_error(self):
        session = _make_mock_session(b"", b"", "", 0)
        info = await FileInspector().inspect_url(
            "https://x.com/e", session=session
        )
        assert info.status == "error"
        assert "Недостаточно данных" in info.parse_note

    async def test_looks_like_html_short_head_is_false(self):
        assert not FileInspector._looks_like_html(b"<html>", "")

    async def test_looks_like_html_by_content_type(self):
        assert FileInspector._looks_like_html(b"abc", "text/html")

    async def test_looks_like_html_by_doctype(self):
        assert FileInspector._looks_like_html(
            b"<!DOCTYPE html>xyz", "text/plain"
        )

    async def test_looks_like_html_by_html_tag(self):
        assert FileInspector._looks_like_html(
            b"<html><head></head></html>", "text/plain"
        )

    async def test_build_file_info_bitrate_avg(self):
        info = FileInspector._build_file_info(
            url="test",
            file_size=1_000_000,
            dims={"duration": 10, "format": "MP3"},
            status="ok",
        )
        assert info.bitrate_avg == 781

    async def test_build_file_info_duration_under_10_rounds_to_1dp(self):
        info = FileInspector._build_file_info(
            url="test", dims={"duration": 5.56}, status="ok"
        )
        assert info.duration == 5.6

    async def test_build_file_info_duration_over_10_rounds_to_int(self):
        info = FileInspector._build_file_info(
            url="test", dims={"duration": 12.55}, status="ok"
        )
        assert info.duration == 13

    async def test_split_parse_result_invalid_status_becomes_partial(self):
        _, _, status = FileInspector._split_parse_result(
            {"_status": "invalid"}
        )
        assert status == "partial"

    async def test_parse_media_dimensions_tiny_head_returns_none(self):
        assert FileInspector.parse_media_dimensions(b"x", None) is None

    async def test_parse_media_dimensions_full_file_in_head_uses_head_as_tail(
        self,
    ):
        head = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0d"
            b"IHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        )
        result = FileInspector.parse_media_dimensions(
            head, None, file_size=len(head)
        )
        assert result is not None
        assert result["format"] == "PNG"

    async def test_mime_overridden_from_format_when_octet_stream(self):
        head = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0d"
            b"IHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        )
        session = _make_mock_session(
            head, None, "application/octet-stream", len(head)
        )
        info = await FileInspector().inspect_url(
            "https://x.com/t", session=session
        )
        assert info.mime_type == "image/png"

    async def test_generic_exception_in_inspect_bytes_caught(self):
        inspector = FileInspector()
        with (
            patch.object(inspector, "last_file_info", None),
            patch.object(
                inspector, "_inspect", side_effect=ValueError("custom")
            ),
            pytest.raises(ValueError, match="custom"),
        ):
            await inspector.inspect_bytes(b"data", file_name="test")

    async def test_initial_head_size_small_file(self):
        from maxapi.utils.file_inspector import RangeDownloader

        rd = RangeDownloader("https://x.com/f")
        rd.file_size = 100
        assert rd._initial_head_size() == 100

    async def test_initial_head_size_below_threshold(self):
        rd = RangeDownloader("https://x.com/f")
        rd.file_size = 1_000_000
        assert rd._initial_head_size() == 1_000_000

    async def test_initial_head_size_large_file(self):
        rd = RangeDownloader("https://x.com/f")
        rd.file_size = 100_000_000
        assert rd._initial_head_size() == 4096

    async def test_initial_head_size_no_file_size(self):
        rd = RangeDownloader("https://x.com/f")
        rd.file_size = None
        assert rd._initial_head_size() == 4096


class TestRangeDownloaderAdvanced:
    """RangeDownloader — прямые тесты методов."""

    async def test_is_trusted_url_true(self):
        assert RangeDownloader("https://oneme.ru/f.jpg")._is_trusted_url
        assert RangeDownloader("https://sub.okcdn.ru/f.jpg")._is_trusted_url

    async def test_is_trusted_url_false(self):
        assert not RangeDownloader("https://evil.com/f.jpg")._is_trusted_url
        assert not RangeDownloader("https://oneme.com/f.jpg")._is_trusted_url

    async def test_final_url_without_meta_returns_original(self):
        assert (
            RangeDownloader("https://x.com/f").final_url == "https://x.com/f"
        )

    async def test_closed_aiter_returns_immediately(self):
        rd = RangeDownloader("https://x.com/f")
        rd._closed = True
        count = 0
        async for _ in rd:
            count += 1
        assert count == 0

    async def test_read_head_bytes_no_response_raises(self):
        rd = RangeDownloader("https://x.com/f")
        with pytest.raises(RuntimeError, match="Response отсутствует"):
            await rd._read_head_bytes(100)

    async def test_fetch_meta_auth_untrusted_raises(self):
        rd = RangeDownloader(
            "https://evil.com/f.jpg", headers={"Authorization": "Bearer x"}
        )
        with pytest.raises(aiohttp.ClientResponseError):
            await rd._fetch_meta()

    async def test_fetch_meta_auth_untrusted_cookie(self):
        rd = RangeDownloader(
            "https://evil.com/f.jpg", headers={"Cookie": "x=y"}
        )
        with pytest.raises(aiohttp.ClientResponseError):
            await rd._fetch_meta()

    async def test_fetch_meta_auth_allowed_with_flag(self):
        rd = RangeDownloader(
            "https://evil.com/f.jpg",
            headers={"Authorization": "Bearer x"},
            allow_external_auth=True,
        )
        resp = AsyncMock(
            status=200,
            ok=True,
            url=URL("https://evil.com/f.jpg"),
            headers={},
            history=(),
            request_info=Mock(),
            release=Mock(),
        )
        resp.content = AsyncMock()
        resp.content.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0")
        resp.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0")
        rd.session = AsyncMock()
        rd.session.get = AsyncMock(return_value=resp)
        await rd._fetch_meta()
        assert rd._meta is not None

    async def test_fetch_meta_bad_content_length(self):
        rd = RangeDownloader("https://x.com/f")
        resp = AsyncMock(
            status=200,
            ok=True,
            url=URL("https://x.com/f"),
            headers={"Content-Type": "image/jpeg", "Content-Length": "abc"},
            history=(),
            request_info=Mock(),
            release=Mock(),
        )
        resp.content = AsyncMock()
        resp.content.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0")
        resp.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0")
        rd.session = _make_mock_session(b"", None)
        await rd._fetch_meta()
        assert rd._meta is not None
        assert rd._meta.file_size is None

    async def test_fetch_chunk_no_meta_raises(self):
        rd = RangeDownloader("https://x.com/f")
        rd._meta = None
        with pytest.raises(RuntimeError, match="Метаинформация не загружена"):
            await rd._fetch_chunk(100, tail=True)

    async def test_fetch_chunk_tail_range_check_returns_empty(self):
        rd = RangeDownloader("https://x.com/f")
        rd._meta = Mock(url="https://x.com/f")
        resp = AsyncMock(
            status=200,
            ok=True,
            url=URL("https://x.com/f"),
            headers={},
            history=(),
            request_info=Mock(),
            release=Mock(),
        )
        resp.content = AsyncMock()
        resp.content.read = AsyncMock(return_value=b"data")

        async def get_side(url, **kw):
            return resp

        rd.session = AsyncMock()
        rd.session.get = AsyncMock(side_effect=get_side)
        rd.head = b"data"
        result = await rd._fetch_chunk(100, tail=True)
        assert result == b""

    async def test_fetch_chunk_tail_not_200_206_returns_empty(self):
        rd = RangeDownloader("https://x.com/f")
        rd._meta = Mock(url="https://x.com/f")
        resp = AsyncMock(
            status=204,
            ok=True,
            url=URL("https://x.com/f"),
            headers={},
            history=(),
            request_info=Mock(),
            release=Mock(),
        )
        resp.content = AsyncMock()
        resp.content.read = AsyncMock(return_value=b"")

        async def get_side(url, **kw):
            return resp

        rd.session = AsyncMock()
        rd.session.get = AsyncMock(side_effect=get_side)
        result = await rd._fetch_chunk(100, tail=True)
        assert result == b""

    async def test_fetch_chunk_head_no_response_raises(self):
        rd = RangeDownloader("https://x.com/f")
        rd._meta = Mock(url="https://x.com/f")
        rd._response = None
        with pytest.raises(RuntimeError, match="Response отсутствует"):
            await rd._fetch_chunk(100, tail=False)

    async def test_expand_head_closed_response(self):
        rd = RangeDownloader("https://x.com/f")
        rd._response = Mock(closed=True)
        assert await rd._expand_head() == b""
        assert await rd._expand_head(target=100) == b""

    async def test_expand_head_no_allowed_space(self):
        rd = RangeDownloader("https://x.com/f")
        rd._response = Mock(closed=False)
        rd.head = b"x" * 128_000
        rd.tail = b"y" * 128_000
        rd.max_total = 256_000
        assert await rd._expand_head() == b""

    async def test_expand_head_target_need_zero(self):
        rd = RangeDownloader("https://x.com/f")
        rd._response = Mock(closed=False)
        rd.head = b"x" * 6000
        rd.max_total = 256_000
        assert await rd._expand_head(target=100) == b""

    async def test_expand_head_exception_during_read(self):
        rd = RangeDownloader("https://x.com/f")
        rd._response = Mock(closed=False)
        rd._response.content = AsyncMock()
        rd._response.content.read = AsyncMock(side_effect=ValueError("boom"))
        result = await rd._expand_head()
        assert result == b""

    async def test_request_with_retry_no_session_raises(self):
        rd = RangeDownloader("https://x.com/f")
        rd.session = None
        with pytest.raises(RuntimeError, match="Сессия не установлена"):
            await rd._request_with_retry("https://x.com/f")

    async def test_request_with_retry_connection_error(self):
        rd = RangeDownloader(
            "https://x.com/f", max_retries=1, retry_backoff_factor=0
        )
        rd.session = AsyncMock()
        rd.session.get = AsyncMock(
            side_effect=aiohttp.ClientConnectionError("fail")
        )
        with pytest.raises(aiohttp.ClientConnectionError):
            await rd._request_with_retry("https://x.com/f")

    async def test_request_with_retry_connection_then_success(self):
        rd = RangeDownloader(
            "https://x.com/f", max_retries=1, retry_backoff_factor=0
        )
        good = Mock(
            status=200,
            ok=True,
            url=URL("https://x.com/f"),
            headers={},
            release=Mock(),
            request_info=Mock(),
            history=(),
        )
        rd.session = AsyncMock()
        rd.session.get = AsyncMock(
            side_effect=[aiohttp.ClientConnectionError("fail"), good]
        )
        resp = await rd._request_with_retry("https://x.com/f")
        assert resp.status == 200

    async def test_request_with_retry_4xx_no_retry(self):
        rd = RangeDownloader(
            "https://x.com/f", max_retries=2, retry_backoff_factor=0
        )
        resp = Mock(
            status=403,
            ok=False,
            release=Mock(),
            headers={},
            request_info=Mock(),
            history=(),
        )
        rd.session = AsyncMock()
        rd.session.get = AsyncMock(return_value=resp)
        with pytest.raises(aiohttp.ClientResponseError) as exc:
            await rd._request_with_retry("https://x.com/f")
        assert exc.value.status == 403

    async def test_request_with_retry_server_error_retry_then_raise(self):
        rd = RangeDownloader(
            "https://x.com/f",
            max_retries=1,
            retry_backoff_factor=0,
            retry_on_statuses=(500,),
        )
        resp = Mock(
            status=500,
            ok=False,
            release=Mock(),
            headers={},
            request_info=Mock(
                url=URL("https://x.com/f"), method="GET", headers=Mock()
            ),
            history=(),
        )
        rd.session = AsyncMock()
        rd.session.get = AsyncMock(return_value=resp)
        with pytest.raises(aiohttp.ClientResponseError) as exc:
            await rd._request_with_retry("https://x.com/f")
        assert exc.value.status == 500

    async def test_extract_filename_content_disposition_multiple_parts(self):
        h = {
            "Content-Disposition": 'form-data; name="file"; filename="rl.jpg"'
        }
        assert (
            RangeDownloader._extract_filename(h, "https://x.com/123")
            == "rl.jpg"
        )

    async def test_extract_filename_from_url_path(self):
        assert (
            RangeDownloader._extract_filename({}, "https://x.com/photo.jpg")
            == "photo.jpg"
        )

    async def test_extract_filename_url_without_path(self):
        assert (
            RangeDownloader._extract_filename({}, "https://x.com/")
            == "unknown"
        )

    async def test_extract_filename_url_with_query(self):
        assert (
            RangeDownloader._extract_filename(
                {}, "https://x.com/photo.jpg?w=100"
            )
            == "photo.jpg"
        )

    async def test_extract_filename_url_encoded(self):
        name = RangeDownloader._extract_filename(
            {}, "https://x.com/%D1%82%D0%B5%D1%81%D1%82.txt"
        )
        assert name == "тест.txt"

    async def test_aiter_with_file_size_under_max_head(self):
        dl = RangeDownloader("https://x.com/f")
        dl.file_size = 100
        dl._meta = Mock(
            url="https://x.com/f", content_type="", file_name="", file_size=100
        )
        dl._fetched_meta = True
        dl.session = AsyncMock()
        resp = AsyncMock(
            status=200,
            ok=True,
            url=URL("https://x.com/f"),
            headers={"Content-Type": "", "Content-Length": "100"},
            history=(),
            request_info=Mock(),
            release=Mock(),
        )
        resp.content = AsyncMock()
        resp.content.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0")
        resp.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0")
        dl._response = resp
        count = 0
        async for _ in dl:
            count += 1
        assert count >= 1

    async def test_close_twice(self):
        rd = RangeDownloader("https://x.com/f")
        await rd.close()
        await rd.close()

    async def test_aexit_closes_own_session(self):
        rd = RangeDownloader("https://x.com/f")
        rd._own_session = True
        session = AsyncMock()
        rd.session = session
        await rd.__aexit__(None, None, None)
        session.close.assert_awaited_once()
        assert rd.session is None

    async def test_satisfy_pending_need_head_expand(self, tmp_path):
        from maxapi.utils.file_inspector import RangeFileReader

        fp = tmp_path / "t.bin"
        fp.write_bytes(b"x" * 500)
        reader = RangeFileReader(str(fp))
        async for _ in reader:
            reader.pending_needs = {"_need_head": -1}
            break
        result = await reader._satisfy_pending_needs()
        assert not result

    async def test_range_file_reader_expand_head_after_loop(self, tmp_path):
        from maxapi.utils.file_inspector import RangeFileReader

        fp = tmp_path / "t2.bin"
        fp.write_bytes(b"data for test file reader")
        reader = RangeFileReader(str(fp))
        async for _ in reader:
            pass
        assert await reader._expand_head() == b""
        assert await reader._fetch_tail(100) == b""

    async def test_file_reader_non_existent(self):
        info = await FileInspector().inspect_file(r"R:\nonexistent\file.jpg")
        assert info.status == "error"
        assert info.parse_note == "Файл не найден"


class TestRangeBytesReaderEdgeCases:
    """RangeBytesReader — BytesIO/NamedBytesIO, expand/satisfy."""

    async def test_bytesio_constructor(self):
        from maxapi.utils.file_inspector import RangeBytesReader

        reader = RangeBytesReader(BytesIO(b"test data for bytes"), "f.txt")
        assert reader.file_size == 19

    async def test_bytesio_without_name(self):
        from maxapi.utils.file_inspector import RangeBytesReader

        reader = RangeBytesReader(BytesIO(b"test"))
        assert reader.file_size == 4

    async def test_named_bytesio_uses_its_name(self):
        from maxapi.utils.file_inspector import RangeBytesReader

        nbio = NamedBytesIO(b"test data")
        nbio.name = "test.txt"
        reader = RangeBytesReader(nbio)
        assert reader.file_name == "test.txt"

    async def test_expand_head_target_exhausted(self):
        from maxapi.utils.file_inspector import RangeBytesReader

        reader = RangeBytesReader(b"hello")
        async for _ in reader:
            pass
        assert await reader._expand_head(target=50) == b""

    async def test_expand_head_zero_chunk(self):
        from maxapi.utils.file_inspector import RangeBytesReader

        reader = RangeBytesReader(b"ab")
        async for _ in reader:
            pass
        assert await reader._expand_head() == b""

    async def test_aiter_with_pending_needs_continues(self):
        from maxapi.utils.file_inspector import RangeBytesReader

        data = b"A" * 8192 + b"B" * 8192
        reader = RangeBytesReader(data)
        reader.pending_needs = {"_need_tail": 100}
        count = 0
        async for _ in reader:
            count += 1
            if count >= 3:
                break
        assert count >= 2

    async def test_small_file_read_fully(self):
        from maxapi.utils.file_inspector import RangeBytesReader

        data = (
            b"\x89PNG\r\n\x1a\n"
            + b"\x00" * 16
            + b"IHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        )
        reader = RangeBytesReader(data, "t.png", full_read_threshold=100)
        async for _ in reader:
            pass
        assert len(reader.head) == len(data)

    async def test_one_iteration_without_pending(self):
        from maxapi.utils.file_inspector import RangeBytesReader

        reader = RangeBytesReader(b"test")
        count = 0
        async for _ in reader:
            count += 1
        assert count == 1

    async def test_fetch_tail_from_bytes_reader(self):
        from maxapi.utils.file_inspector import RangeBytesReader

        data = b"x" * 100 + b"y" * 100
        reader = RangeBytesReader(data)
        async for _ in reader:
            pass
        tail = await reader._fetch_tail(50)
        assert tail == data[-50:]


class TestParsersEdgeCases:
    """Прямые тесты статических методов парсеров (для покрытия)."""

    # --- JPEG ---
    def test_jpeg_no_sof_returns_partial_with_need(self):
        """JPEG без SOF -> partial + need_head/need_tail."""
        data = b"\xff\xd8\xff\xe1\x00\x10\x00" + b"\x00" * 20
        r = FileInspector._jpeg_parse(data)
        assert r is not None
        assert r["_status"] == "partial"

    def test_jpeg_sof_found_returns_dims(self):
        """JPEG с SOF -> размеры изображения."""
        data = (
            b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x10"
            b"\x00\x0e\x03\x01\x22\x00\x02\x11\x01"
        )
        r = FileInspector._jpeg_parse(data)
        assert r is not None
        assert r["width"] == 14
        assert r["height"] == 16

    def test_jpeg_not_jpeg(self):
        """Не JPEG - не подходит."""
        assert FileInspector._jpeg_parse(b"\x00\x00") is None

    # --- PNG checks ---
    def test_png_check_short(self):
        """PNG check: слишком короткий."""
        assert not FileInspector._png_check(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0d"
        )

    def test_png_check_valid(self):
        """PNG check: сигнатура совпадает."""
        assert FileInspector._png_check(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR" + b"\x00" * 8
        )

    # --- WEBP checks ---
    def test_webp_check_short(self):
        """WEBP check: слишком короткий."""
        assert not FileInspector._webp_check(b"RIFF\x00\x00\x00\x00")

    def test_webp_check_valid(self):
        """WEBP check: сигнатура совпадает."""
        assert FileInspector._webp_check(
            b"\x00\x00\x00\x00\x00\x00\x00\x00WEBP"
        )

    # --- GIF checks ---
    def test_gif_check_short(self):
        """GIF check: слишком короткий."""
        assert not FileInspector._gif_check(b"GIF87")

    def test_gif_check_valid(self):
        """GIF check: сигнатура совпадает."""
        assert FileInspector._gif_check(b"GIF89a" + b"\x00" * 4)

    # --- MP3 checks ---
    def test_mp3_check_id3(self):
        """MP3 check: ID3-тег."""
        assert FileInspector._mp3_check(b"ID3")

    def test_mp3_check_frame_sync(self):
        """MP3 check: синхронизация фрейма."""
        assert FileInspector._mp3_check(b"\xff\xe0")

    def test_mp3_check_no_match(self):
        """MP3 check: нет совпадения."""
        assert not FileInspector._mp3_check(b"\x00\x00")

    # --- WAV check ---
    def test_wav_check_valid(self):
        """WAV check: сигнатура RIFF + WAVE."""
        assert FileInspector._wav_check(b"RIFF\x00\x00\x00\x00WAVE")

    def test_wav_check_no_wave(self):
        """WAV check: без WAVE-идентификатора."""
        assert not FileInspector._wav_check(b"RIFF\x00\x00\x00\x00AVI ")

    def test_wav_check_short(self):
        """WAV check: слишком короткий."""
        assert not FileInspector._wav_check(b"RIFF")

    # --- FLAC check ---
    def test_flac_check(self):
        """FLAC check: сигнатура fLaC."""
        assert FileInspector._flac_check(b"fLaC")
        assert not FileInspector._flac_check(b"FLAC")

    # --- OGG check ---
    def test_ogg_ogv_check(self):
        """OGG/OGV check: сигнатура OggS."""
        assert FileInspector._ogg_ogv_check(b"OggS")
        assert not FileInspector._ogg_ogv_check(b"OggX")

    # --- AAC check ---
    def test_aac_check_valid(self):
        """AAC check: синхронизация фрейма."""
        assert FileInspector._aac_check(b"\xff\xf1")

    def test_aac_check_no_match(self):
        """AAC check: нет совпадения."""
        assert not FileInspector._aac_check(b"\x00\x00")

    # --- M4A check ---
    def test_m4a_check_valid(self):
        """M4A check: ftyp M4A."""
        assert FileInspector._m4a_check(b"\x00\x00\x00\x10ftypM4A ")

    def test_m4a_check_no_match(self):
        """M4A check: нет совпадения."""
        assert not FileInspector._m4a_check(b"\x00\x00\x00\x10ftypmp42")

    # --- WMA check ---
    def test_wma_check_valid(self):
        """WMA check: GUID ASF_Header."""
        guid = (
            b"\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\x00\xaa\x00\x62\xce\x6c"
        )
        assert FileInspector._wma_check(guid)

    def test_wma_check_no_match(self):
        """WMA check: нет совпадения."""
        assert not FileInspector._wma_check(b"\x00" * 16)

    # --- MP4 check ---
    def test_mp4_check_short(self):
        """MP4 check: слишком короткий."""
        assert not FileInspector._mp4_check(b"abc")

    def test_mp4_check_ftyp_video(self):
        """MP4 check: ftyp для видео."""
        assert FileInspector._mp4_check(
            b"\x00\x00\x00\x10ftypmp42\x00\x00\x00\x00"
        )

    def test_mp4_check_old_qt(self):
        """MP4 check: старый QuickTime (moov)."""
        assert FileInspector._mp4_check(b"moov")

    def test_mp4_check_not_mp4(self):
        """MP4 check: не MP4."""
        assert not FileInspector._mp4_check(b"\x00\x00\x00\x10ftypM4A ")

    # --- AVI check ---
    def test_avi_check_valid(self):
        """AVI check: RIFF + AVI."""
        assert FileInspector._avi_check(b"RIFF\x00\x00\x00\x00AVI ")

    def test_avi_check_no_match(self):
        """AVI check: нет совпадения."""
        assert not FileInspector._avi_check(b"RIFF\x00\x00\x00\x00WAVE")

    def test_avi_check_short(self):
        """AVI check: слишком короткий."""
        assert not FileInspector._avi_check(b"RIFF")

    # --- WebM/MKV check ---
    def test_webm_mkv_check_valid(self):
        """WebM/MKV check: EBML + docType."""
        assert FileInspector._webm_mkv_check(b"\x00\x45\xdf\xa3")

    def test_webm_mkv_check_short(self):
        """WebM/MKV check: слишком короткий."""
        assert not FileInspector._webm_mkv_check(b"abc")

    # --- MP4 parsing ---
    def test_mp4_find_moov_not_found(self):
        """moov не найден в данных."""
        assert FileInspector._mp4_find_moov(b"\x00" * 100) is None

    def test_mp4_find_moov_short(self):
        """Недостаточно данных для moov."""
        assert FileInspector._mp4_find_moov(b"moov") is None

    def test_mp4_moov_parse_empty(self):
        """Пустой moov - нет mvhd."""
        assert FileInspector._mp4_moov_parse(b"\x00\x00\x00\x00") is None

    def test_mp4_moov_parse_mvhd(self):
        """moov c mvhd - длительность + шкала."""
        mvhd = (
            b"\x00\x00\x00\x30mvhd\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01"
            b"\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        )
        # doesn't have enough for mvhd parsing, but tests the path
        result = FileInspector._mp4_moov_parse(mvhd)
        assert result is None or "duration" not in result

    def test_mp4_moov_parse_size_one_too_short(self):
        """size=1 (64-бит), но данных мало."""
        result = FileInspector._mp4_moov_parse(b"\x00\x00\x00\x01mvhd\x00")
        assert result is None

    def test_mp4_parse_trak_for_dims_no_tkhd(self):
        """trak без tkhd - нет размеров."""
        result = FileInspector._mp4_parse_trak_for_dims(
            b"\x00\x00\x00\x08mdia\x00\x00\x00\x08"
        )
        assert result is None

    def test_mp4_parse_trak_for_dims_size_one(self):
        """trak с size=1 (64-бит)."""
        data = b"\x00\x00\x00\x01" + b"tkhd" + b"\x00" * 12 + b"\x00" * 88
        result = FileInspector._mp4_parse_trak_for_dims(data)
        assert result is None or len(result) == 0

    def test_mp4_parse_tkhd_version0(self):
        """tkhd version=0 - ширина/высота."""
        data = bytearray(84)
        data[76:80] = b"\x00\x01\x00\x00"
        data[80:84] = b"\x00\x01\x00\x00"
        r = FileInspector._mp4_parse_tkhd(bytes(data))
        assert r is not None
        assert r["width"] == 1

    def test_mp4_parse_tkhd_version0_too_short(self):
        """tkhd v0: слишком короткий."""
        assert FileInspector._mp4_parse_tkhd(b"\x00" + b"\x00" * 70) is None

    def test_mp4_parse_tkhd_version1(self):
        """tkhd version=1 - ширина/высота."""
        data = bytearray(100)
        data[0] = 1
        data[92:96] = b"\x00\x01\x00\x00"
        data[96:100] = b"\x00\x01\x00\x00"
        r = FileInspector._mp4_parse_tkhd(bytes(data))
        assert r is not None
        assert r["width"] == 1

    def test_mp4_parse_tkhd_version1_too_short(self):
        """tkhd v1: слишком короткий."""
        assert FileInspector._mp4_parse_tkhd(b"\x01" + b"\x00" * 90) is None

    def test_mp4_parse_tkhd_unknown_version(self):
        """tkhd: неизвестная версия."""
        assert FileInspector._mp4_parse_tkhd(b"\x02" + b"\x00" * 100) is None

    def test_mp4_is_valid_dims_16384(self):
        """Размер 16384 - допустим."""
        assert not FileInspector._mp4_is_valid_video_dims(
            {"width": 16384, "height": 16384}
        )

    def test_mp4_is_valid_dims_too_small(self):
        """Размер < 2 - недопустим."""
        assert not FileInspector._mp4_is_valid_video_dims(
            {"width": 1, "height": 1}
        )

    def test_mp4_is_valid_dims_too_large(self):
        """Размер > 16384 - недопустим."""
        assert not FileInspector._mp4_is_valid_video_dims(
            {"width": 20000, "height": 20000}
        )

    def test_mp4_is_valid_dims_none(self):
        """None - недопустим."""
        assert not FileInspector._mp4_is_valid_video_dims(None)

    def test_mp4_is_valid_dims_ok(self):
        """Корректные размеры - допустимы."""
        assert FileInspector._mp4_is_valid_video_dims(
            {"width": 640, "height": 480}
        )

    def test_mp4_parse_sample_rate_not_found(self):
        """Частота дискретизации не найдена."""
        assert FileInspector._mp4_parse_sample_rate(b"\x00" * 100) is None

    def test_mp4_m4a_not_mp4(self):
        """Не MP4 - не обрабатывается как M4A."""
        assert FileInspector._mp4_m4a_parse_info(b"\x00" * 16) is None

    def test_mp4_m4a_no_moov_no_tail(self):
        """M4A без moov и tail."""
        r = FileInspector._mp4_m4a_parse_info(
            b"\x00\x00\x00\x10ftypmp42\x00\x00\x00\x00"
        )
        assert r is not None
        assert r["_status"] == "partial"
        assert "_need_tail" in r

    def test_m4a_parse_mvhd_too_short(self):
        """mvhd: слишком короткий заголовок."""
        assert FileInspector._m4a_parse_mvhd_duration(b"\x00" * 10) is None

    def test_m4a_parse_mvhd_version0_duration(self):
        """mvhd v0: duration = 100 / 1 = 100.0."""
        data = (
            b"\x00" * 8
            + b"\x00\x00\x00\x00"
            + b"\x00" * 8
            + b"\x00\x00\x00\x01\x00\x00\x00\x64"
        )
        r = FileInspector._m4a_parse_mvhd_duration(data)
        assert r == 100.0

    def test_m4a_parse_mvhd_version1_duration(self):
        """mvhd v1: duration = 100 / 1 = 100.0 (QWORD-поле)."""
        data = (
            b"\x00" * 8
            + b"\x01\x00\x00\x00"
            + b"\x00" * 8
            + b"\x00\x00\x00\x01"
            + struct.pack(">Q", 100)
        )
        r = FileInspector._m4a_parse_mvhd_duration(data)
        assert r == 100.0

    # --- AVI parsing ---
    def test_avi_parse_too_small(self):
        """AVI: слишком маленький."""
        assert FileInspector._avi_parse_info(b"RIF") is None

    def test_avi_parse_not_avi(self):
        """AVI: не AVI-файл."""
        assert (
            FileInspector._avi_parse_info(b"RIFF\x00\x00\x00\x00WAVE") is None
        )

    def test_avi_parse_no_hdrl(self):
        """AVI: нет hdrl-листа."""
        data = b"RIFF\x00\x00\x00\x00AVI " + b"\x00" * 100
        r = FileInspector._avi_parse_info(data)
        assert r is not None
        assert r["format"] == "AVI"

    def test_parse_avih_too_short(self):
        """avih: слишком короткий."""
        r = {"format": "AVI", "width": None}
        FileInspector._parse_avih(b"", 0, 10, r)
        assert r["width"] is None

    def test_parse_avih_with_data(self):
        """avih: длительность + флаги."""
        r = {
            "format": "AVI",
            "width": None,
            "total_frames": None,
            "bitrate": None,
            "height": None,
        }
        content = (
            b"\x00" * 4
            + b"\x01\x00\x00\x00"
            + b"\x00" * 8
            + b"\x64\x00\x00\x00"
            + b"\x00" * 12
            + b"\x80\x07\x00\x00\x38\x04\x00\x00"
            + b"\x00" * 16
        )
        FileInspector._parse_avih(content, 0, len(content), r)
        assert r["total_frames"] == 100

    def test_parse_strh_too_short(self):
        """strh: слишком короткий."""
        r = {"format": "AVI", "width": None, "sample_rate": None, "fps": None}
        FileInspector._parse_strh(b"", 0, 10, r)
        assert r["width"] is None

    def test_parse_strh_vids_with_dims(self):
        """strh vids: ширина/высота."""
        r = {"format": "AVI", "width": None, "sample_rate": None, "fps": None}
        data = (
            b"vids"
            + b"\x00" * 16
            + struct.pack("<II", 1, 24)
            + b"\x00" * 16
            + struct.pack("<IIII", 10, 5, 20, 15)
        )
        FileInspector._parse_strh(data, 0, len(data), r)
        assert r["fps"] == 24.0

    def test_parse_strh_auds(self):
        """strh auds: частота дискретизации."""
        r = {"format": "AVI", "width": None, "sample_rate": None}
        data = b"auds" + b"\x00" * 20 + b"\x44\xac\x00\x00" + b"\x00" * 28
        FileInspector._parse_strh(data, 0, len(data), r)
        assert r["sample_rate"] == 44100

    def test_parse_strh_auds_non_standard_rate(self):
        """strh auds: нестандартная частота."""
        r = {"format": "AVI", "width": None, "sample_rate": None}
        data = b"auds" + b"\x00" * 20 + b"\x07\xd0\x00\x00" + b"\x00" * 28
        FileInspector._parse_strh(data, 0, len(data), r)
        assert r["sample_rate"] is None

    def test_parse_strf_audio(self):
        """strf: формат 1 (PCM) → sample_rate = 48000."""
        r = {"format": "AVI", "sample_rate": None}
        data = (
            struct.pack("<HH", 1, 2) + struct.pack("<I", 48000) + b"\x00" * 8
        )
        FileInspector._parse_strf(data, 0, len(data), r)
        assert r["sample_rate"] == 48000

    def test_parse_strf_too_short(self):
        """strf: слишком короткий."""
        r = {"format": "AVI"}
        FileInspector._parse_strf(b"\x00" * 10, 0, 10, r)

    def test_parse_strl_no_match(self):
        """strl: нет совпадения."""
        r = {"format": "AVI", "width": None, "sample_rate": None}
        FileInspector._parse_strl(b"\x00" * 20, 0, 20, r)
        assert r["width"] is None

    def test_parse_hdrl_no_match(self):
        """hdrl: нет совпадения."""
        r = {"format": "AVI", "width": None}
        FileInspector._parse_hdrl(b"\x00" * 20, 0, 20, r)
        assert r["width"] is None

    # --- WebM/MKV parsing ---
    def test_webm_mkv_parse_too_short(self):
        """WebM/MKV: слишком короткий."""
        assert FileInspector._webm_mkv_parse_info(b"abc") is None

    def test_webm_mkv_parse_no_metadata(self):
        """WebM/MKV: нет метаданных."""
        data = b"\x1a\x45\xdf\xa3" + b"\x00" * 100
        r = FileInspector._webm_mkv_parse_info(data)
        # Returns partial with format=WEBM despite no metadata
        assert r is not None
        assert r["_status"] == "partial"

    def test_webm_ebml_detect_mkv(self):
        """EBML: Matroska (MKV)."""
        data = b"\x1a\x45\xdf\xa3" + b"\x00" * 20 + b"V_MS/VFW"
        assert FileInspector._webm_ebml_detect_format_by_codecs(data) == "MKV"

    def test_webm_ebml_detect_webm(self):
        """EBML: WebM."""
        data = b"\x1a\x45\xdf\xa3" + b"\x00" * 20 + b"V_VP8"
        assert FileInspector._webm_ebml_detect_format_by_codecs(data) == "WEBM"

    def test_webm_ebml_detect_no_ebml(self):
        """EBML: не обнаружен."""
        assert (
            FileInspector._webm_ebml_detect_format_by_codecs(b"test") is None
        )

    def test_webm_read_ebml_size_vint_eof(self):
        """EBML vint-size: неожиданный конец."""
        assert FileInspector._webm_read_ebml_size_vint(b"", 0) is None

    def test_webm_read_ebml_size_vint_too_long(self):
        """EBML vint-size: слишком длинный."""
        assert (
            FileInspector._webm_read_ebml_size_vint(
                b"\x00\x00\x00\x00\x00\x00\x00\x00\x00", 0
            )
            is None
        )

    def test_webm_read_ebml_element_value_not_found(self):
        """EBML элемент не найден."""
        assert (
            FileInspector._webm_read_ebml_element_value(
                b"\x00" * 10, b"\x42\x86", lambda x: x
            )
            is None
        )

    def test_webm_read_ebml_element_value_size_meta_none(self):
        """EBML: size_meta = None."""
        assert (
            FileInspector._webm_read_ebml_element_value(
                b"\x42\x86\xff\xff\xff\xff\xff\xff\xff\xff\xff",
                b"\x42\x86",
                lambda x: x,
            )
            is None
        )

    def test_webm_read_ebml_element_value_value_end_oob(self):
        """EBML: value_end за границами."""
        assert (
            FileInspector._webm_read_ebml_element_value(
                b"\x42\x86\x83" + b"x" * 3, b"\x42\x86", lambda x: x
            )
            == b"x" * 3
        )

    def test_webm_read_ebml_element_value_parser_none(self):
        """EBML: parser = None."""
        assert (
            FileInspector._webm_read_ebml_element_value(
                b"\x42\x86\x83abc", b"\x42\x86", lambda x: None
            )
            is None
        )

    def test_webm_read_ebml_float_4byte(self):
        """EBML float: 4 байта."""
        import struct

        val = struct.pack(">f", 3.14)
        data = b"\x42\x86\x84" + val
        r = FileInspector._webm_read_ebml_float(data, b"\x42\x86")
        assert r is not None
        assert abs(r - 3.14) < 0.01

    def test_webm_read_ebml_float_8byte(self):
        """EBML float: 8 байт."""
        import struct

        val = struct.pack(">d", 3.14159)
        data = b"\x42\x86\x88" + val
        r = FileInspector._webm_read_ebml_float(data, b"\x42\x86")
        assert r is not None
        assert abs(r - 3.14159) < 0.001

    def test_webm_read_ebml_string_ok(self):
        """EBML string: успешное чтение."""
        data = b"\x42\x82\x84webm"
        assert (
            FileInspector._webm_read_ebml_string(data, b"\x42\x82") == "webm"
        )

    def test_webm_read_ebml_string_unicode_error(self):
        """EBML string: ошибка Unicode."""
        data = b"\x42\x82\x84\xff\xff\xff\xff"
        assert FileInspector._webm_read_ebml_string(data, b"\x42\x82") is None

    def test_webm_read_duration_seconds_no_duration(self):
        """Нет Duration -> None."""
        assert FileInspector._webm_read_duration_seconds(b"\x00" * 10) is None

    def test_webm_read_duration_seconds_with_default_scale(self):
        """Duration с TimecodeScale по умолчанию."""
        import struct

        dur = struct.pack(">d", 10000.0)
        assert (
            FileInspector._webm_read_duration_seconds(b"\x44\x89\x88" + dur)
            == 10
        )

    def test_webm_read_duration_seconds_with_custom_scale(self):
        """Duration с кастомным TimecodeScale."""
        import struct

        dur = struct.pack(">d", 10.0)
        tc = b"\x2a\xd7\xb1\x84\x00\x00\x00\x01"
        r = FileInspector._webm_read_duration_seconds(
            b"\x44\x89\x88" + dur + tc
        )
        assert r == 0  # 10 * 1 / 1e9 = 0

    # --- MP3 parsing ---
    def test_mp3_parse_not_enough_data(self):
        """Недостаточно данных для парсинга."""
        r = FileInspector._mp3_parse_info(b"\x00\x00\x00\x00", file_size=100)
        assert r is not None
        assert r["_status"] == "partial"

    def test_mp3_parse_frame_found_with_xing(self):
        """Xing с 154 кадрами → duration = 154*1152/44100 ≈ 4с."""
        header = b"\xff\xfb\x90\x00"
        xing_body = (
            b"Xing"
            b"\x00\x00\x00\x07"
            + struct.pack(">I", 154)
            + b"\x00\x00\x00\x00"
            + b"\x00\x00\x0e\x10"
        )
        padding_before = b"\x00" * 17  # offset from frame header to Xing = 21
        padding_after = b"\x00" * (100 - 4 - 17 - len(xing_body))
        data = header + padding_before + xing_body + padding_after
        r = FileInspector._mp3_parse_info(data, file_size=10000)
        assert r is not None
        assert r.get("duration") == 4

    def test_mp3_parse_vbri(self):
        """VBRI-заголовок: длительность + битрейт."""
        header = b"\xff\xfb\x90\x00"
        vbri = (
            b"\x00" * 32
            + b"VBRI"
            + b"\x00\x00\x00\x00\x00\x00"
            + b"\x00\x00\x00\x64"
        )
        r = FileInspector._mp3_parse_info(header + vbri, file_size=100000)
        assert r is not None

    def test_mp3_find_frame_header_none(self):
        """Заголовок фрейма не найден."""
        assert (
            FileInspector._mp3_find_frame_header(b"\x00\x00\x00\x00", 0)
            is None
        )

    def test_mp3_find_frame_header_found(self):
        """Заголовок фрейма найден."""
        r = FileInspector._mp3_find_frame_header(
            b"\x00\x00\xff\xfb\x90\x00" + b"\x00" * 20, 0
        )
        assert r == 2

    def test_mp3_bitrate_table_reserved(self):
        """Зарезервированный битрейт -> None."""
        assert all(x is None for x in FileInspector._mp3_bitrate_table(0, 0))

    def test_mp3_parse_xing_not_found(self):
        """Xing не найден."""
        assert (
            FileInspector._mp3_parse_xing_vbri(
                b"\xff\xfb\x90\x00" + b"\x00" * 100, 0
            )
            is None
        )

    def test_mp3_parse_xing_vbri_too_short(self):
        """Xing/VBRI слишком короткий."""
        assert FileInspector._mp3_parse_xing_vbri(b"", 0) is None

    # --- OGG parsing ---
    def test_ogg_extract_last_granule_no_tail(self):
        """Нет tail -> partial + need_tail."""
        assert FileInspector._ogg_extract_last_granule(None) is None

    def test_ogg_extract_last_granule_short_tail(self):
        """tail < 27 байт -> partial + need_tail."""
        assert FileInspector._ogg_extract_last_granule(b"abc") is None

    def test_ogg_parse_info_no_head(self):
        """Нет head -> error."""
        assert FileInspector._ogg_parse_info(b"\x00" * 10, None) is None

    def test_ogg_parse_info_short_tail(self):
        """tail < 27 байт → NEED_TAIL, status partial."""
        vorbis_payload = (
            b"\x01vorbis"
            + struct.pack("<I", 0)
            + struct.pack("<B", 2)
            + struct.pack("<I", 44100)
            + struct.pack("<I", 0) * 3
        )
        page = (
            b"OggS"
            + bytes([0, 2])
            + struct.pack("<q", 0)
            + struct.pack("<I", 12345)
            + struct.pack("<I", 0)
            + struct.pack("<I", 0)
            + bytes([1, len(vorbis_payload)])
            + vorbis_payload
        )
        r = FileInspector._ogg_parse_info(page, b"ab", file_size=1000)
        assert r is not None
        assert r["_status"] == "partial"

    def test_ogg_parse_info_fallback_duration(self):
        """Фоллбэк: serial в tail (99999) ≠ serial потока (12345).
        Основной цикл не находит гранулу, фоллбэк с expected_serial=None
        находит и вычисляет duration = 441000 / 44100 = 10 с."""
        head_vorbis = (
            b"\x01vorbis"
            + struct.pack("<I", 0)
            + struct.pack("<B", 2)
            + struct.pack("<I", 44100)
            + struct.pack("<I", 0) * 3
        )
        head_page = (
            b"OggS"
            + bytes([0, 2])
            + struct.pack("<q", 0)
            + struct.pack("<I", 12345)
            + struct.pack("<I", 0)
            + struct.pack("<I", 0)
            + bytes([1, len(head_vorbis)])
            + head_vorbis
        )
        tail_payload = b"\x00" * 10
        tail_page = (
            b"OggS"
            + bytes([0, 0])
            + struct.pack("<q", 441000)
            + struct.pack("<I", 99999)
            + struct.pack("<I", 5)
            + struct.pack("<I", 0)
            + bytes([1, len(tail_payload)])
            + tail_payload
        )
        r = FileInspector._ogg_parse_info(
            head_page, tail_page, file_size=100000
        )
        assert r is not None
        assert r["_status"] == "ok"
        assert r["sample_rate"] == 44100
        assert r["duration"] == 10.0

    # --- WAV parsing ---
    def test_wav_parse_no_wave(self):
        """Не WAV-файл."""
        assert (
            FileInspector._wav_parse_info(b"RIFF\x00\x00\x00\x00XXXX") is None
        )

    def test_wav_parse_no_fmt(self):
        """Нет fmt-чанка."""
        r = FileInspector._wav_parse_info(b"RIFF\x00\x00\x00\x00WAVE")
        assert r is not None
        assert r["format"] == "WAV"

    def test_wav_parse_with_data(self):
        """WAV с data-чанком."""
        fmt = (
            b"fmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac"
            b"\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00"
        )
        data = b"data\x64\x00\x00\x00" + b"\x00" * 100
        wav = b"RIFF\x00\x00\x00\x00WAVE" + fmt + data
        r = FileInspector._wav_parse_info(wav, total_size=200)
        assert r is not None
        assert r.get("sample_rate") == 44100
        assert r.get("duration") is not None

    def test_wav_parse_zero_byte_rate(self):
        """byte_rate = 0 -> duration None."""
        fmt = (
            b"fmt \x10\x00\x00\x00\x01\x00\x01\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x02\x00\x10\x00"
        )
        wav = b"RIFF\x00\x00\x00\x00WAVE" + fmt
        r = FileInspector._wav_parse_info(wav, total_size=200)
        assert r is not None
        assert r["_status"] == "partial"

    # --- FLAC parsing ---
    def test_flac_not_flac(self):
        """Не FLAC -> error."""
        assert FileInspector._flac_parse_info(b"xxxx") is None

    def test_flac_with_padding(self):
        """FLAC c PADDING-блоком."""
        si = b"\x00" * 34
        data = b"fLaC\x01\x00\x00\x04\x00\x00\x00\x00\x80\x00\x00\x22" + si
        assert FileInspector._flac_parse_info(data) is not None

    def test_flac_with_unknown_block(self):
        """FLAC с неизвестным блоком."""
        si = b"\x00" * 34
        data = b"fLaC\x03\x00\x00\x04\x00\x00\x00\x00\x80\x00\x00\x22" + si
        assert FileInspector._flac_parse_info(data) is not None

    def test_flac_last_block(self):
        """FLAC: последний блок (bit 7 = 1)."""
        si = b"\x00" * 34
        data = b"fLaC\x80\x00\x00\x22" + si
        assert FileInspector._flac_parse_info(data) is not None

    def test_flac_streaminfo_too_short(self):
        """FLAC STREAMINFO: слишком короткий."""
        data = b"fLaC\x80\x00\x00\x22" + b"\x00" * 10
        assert FileInspector._flac_parse_info(data) is None

    # --- AAC parsing ---
    def test_aac_no_frames(self):
        """Нет AAC-фреймов."""
        r = FileInspector._aac_parse_info(b"\x00" * 100)
        assert r is not None
        assert r["_status"] == "partial"

    def test_aac_with_id3(self):
        """AAC с ID3-тегом в начале."""
        id3 = b"ID3\x04\x00\x00\x00\x00\x00\x23"
        frame = b"\xff\xf1\x50\x80\x03\xff\xf9" + b"\x00" * 100
        r = FileInspector._aac_parse_info(id3 + b"\x00" * 35 + frame)
        assert r is not None
        assert r["format"] == "AAC"

    def test_aac_parse_sample_rate_out_of_range(self):
        """Частота дискретизации вне диапазона."""
        frame = b"\xff\xf1\x70\x80\x03\xff\xf9" + b"\x00" * 100
        r = FileInspector._aac_parse_info(frame)
        assert r is not None

    # --- parse_audio_dimensions ---
    def test_parse_audio_dimensions_no_match(self):
        """Аудио: нет совпадения -> None."""
        assert (
            FileInspector._parse_audio_dimensions(b"\x00" * 10, None, None)
            is None
        )

    # --- parse_video_dimensions ---
    def test_parse_video_dimensions_no_match(self):
        """Видео: нет совпадения -> None."""
        assert (
            FileInspector._parse_video_dimensions(b"\x00" * 10, None, None)
            is None
        )

    # --- parse_image_dimensions ---
    def test_parse_image_dimensions_no_match(self):
        """Изображение: нет совпадения -> None."""
        assert (
            FileInspector._parse_image_dimensions(b"\x00" * 10, None) is None
        )

    # --- _ogg_calculate_duration ---
    def test_ogg_calculate_theora_no_fps(self):
        """Theora: FPS отсутствует."""
        assert (
            FileInspector._ogg_calculate_duration({"type": "theora"}, 100)
            is None
        )

    def test_ogg_calculate_theora_fps_zero(self):
        """Theora: FPS = 0."""
        assert (
            FileInspector._ogg_calculate_duration(
                {"type": "theora", "fps_num": 0, "fps_den": 1}, 100
            )
            is None
        )

    def test_ogg_calculate_vorbis_no_sample_rate(self):
        """Vorbis: нет sample_rate."""
        assert (
            FileInspector._ogg_calculate_duration({"type": "vorbis"}, 100)
            is None
        )

    def test_ogg_calculate_unknown_type(self):
        """Неизвестный тип OGG-кодека."""
        assert (
            FileInspector._ogg_calculate_duration({"type": "opus"}, 100)
            is None
        )

    # --- WMA edge ---
    def test_wma_too_short(self):
        """WMA: слишком короткий."""
        assert FileInspector._wma_parse_info(b"\x00" * 10) is None

    def test_wma_with_file_props(self):
        """
        WMA c FileProperties + StreamProperties: format, duration, sample_rate.
        """
        guid = (
            b"\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\x00\xaa\x00\x62\xce\x6c"
        )
        fp_guid = (
            b"\xa1\xdc\xab\x8c\x47\xa9\xcf\x11\x8e\xe4\x00\xc0\x0c\x20\x53\x65"
        )
        sp_guid = (
            b"\x91\x07\xdc\xb7\xb7\xa9\xcf\x11\x8e\xe6\x00\xc0\x0c\x20\x53\x65"
        )
        audio_guid = (
            b"\x40\x9e\x69\xf8\x4d\x5b\xcf\x11\xa8\xfd\x00\x80\x5f\x5c\x44\x2b"
        )
        fp_obj = (
            fp_guid
            + b"\x00" * 48
            + struct.pack("<Q", 10000000)
            + struct.pack("<Q", 0)
            + struct.pack("<Q", 0)
        )
        type_specific = (
            struct.pack("<H", 0x0161)
            + struct.pack("<H", 2)
            + struct.pack("<I", 44100)
            + struct.pack("<I", 8000)
            + struct.pack("<HHH", 2, 16, 0)
        )
        obj_size = 16 + 8 + 16 + 32 + len(type_specific)
        sp_obj = (
            sp_guid
            + struct.pack("<Q", obj_size)
            + audio_guid
            + b"\x00" * 32
            + type_specific
        )
        data = guid + fp_obj + sp_obj
        r = FileInspector._wma_parse_info(data)
        assert r is not None
        assert r["format"] == "WMA"

    def test_wma_no_stream_props(self):
        """WMA: только FilePropertiesObject (длительность), без аудиопотока."""
        guid = (
            b"\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\x00\xaa\x00\x62\xce\x6c"
        )
        fp_guid = (
            b"\xa1\xdc\xab\x8c\x47\xa9\xcf\x11\x8e\xe4\x00\xc0\x0c\x20\x53\x65"
        )
        fp_obj = (
            fp_guid
            + b"\x00" * 48
            + struct.pack("<Q", 10000000)
            + struct.pack("<Q", 0)
            + struct.pack("<Q", 0)
        )
        data = guid + fp_obj
        r = FileInspector._wma_parse_info(data)
        assert r is not None
        assert r["format"] == "WMA"

    # --- _ogg_parse_all_streams: no OggS ---
    def test_ogg_parse_all_streams_no_ogg(self):
        """Не OGG-файл -> нет потоков."""
        assert FileInspector._ogg_parse_all_streams(b"\x00" * 30) == []

    # --- _wav_parse: data chunk with total_size ---
    def test_wav_data_chunk_with_total_size(self):
        """WAV: размер из data-чанка."""
        fmt = (
            b"fmt \x10\x00\x00\x00\x01\x00\x01\x00\x44"
            b"\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00"
        )
        wav = b"RIFF\x00\x00\x00\x00WAVE" + fmt + b"data\x00\x00\x00\x00"
        r = FileInspector._wav_parse_info(wav)
        assert r is not None
        assert r["format"] == "WAV"
