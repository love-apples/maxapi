from __future__ import annotations

"""
Инспекция медиафайлов без полной загрузки.

Модуль читает начало и при необходимости конец файла (локально, по HTTP
или из bytes) и извлекает метаданные: формат, размеры, длительность,
битрейт. Высокоуровневая точка входа — :class:`FileInspector`.
"""

import asyncio
import logging
import mimetypes
import struct
from abc import ABC, abstractmethod
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast
from urllib.parse import unquote, urlparse

import aiohttp
import anyio
from aiohttp import ClientConnectionError, ClientResponse, ClientTimeout
from pydantic import BaseModel

from ..connection.base import NamedBytesIO
from ..types.file_info import FileInfo

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from multidict import CIMultiDictProxy

logger = logging.getLogger("maxapi.fileinfo")

# HTTP-статусы, при которых имеет смысл повторить запрос:
# 429 — Too Many Requests (сервер просит подождать)
# 500 — Internal Server Error (временная ошибка сервера)
# 502 — Bad Gateway (промежуточный прокси не справился)
# 503 — Service Unavailable (сервер перегружен или на обслуживании)
# 504 — Gateway Timeout (промежуточный прокси не дождался ответа)
DEFAULT_RETRY_STATUSES: tuple[int, ...] = (429, 500, 502, 503, 504)

_FORMAT_TO_MIME: dict[str, str] = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "GIF": "image/gif",
    "WEBP": "image/webp",
    "WEBP/VP8": "image/webp",
    "WEBP/VP8L": "image/webp",
    "WEBP/VP8X": "image/webp",
    "MP4": "video/mp4",
    "AVI": "video/x-msvideo",
    "WEBM": "video/webm",
    "OGG": "audio/ogg",
    "OGV": "video/ogg",
    "MP3": "audio/mpeg",
    "AAC": "audio/aac",
    "WAV": "audio/wav",
    "WMA": "audio/x-ms-wma",
    "M4A": "audio/mp4",
    "FLAC": "audio/flac",
    "MKV": "video/x-matroska",
}

# ============================================================================
# [ ] Структуры данных
# ============================================================================


class FetchPlan(BaseModel):
    """
    План частичного чтения файла.

    Attributes:
        initial_head: Размер первого блока с начала файла.
        expand_chunk: Размер блока докачки (0 — без докачки).
        max_head: Верхняя граница размера head.
        min_head: Нижняя граница размера head.
        need_tail: Размер блока с конца (0 — хвост не нужен).
    """

    initial_head: int = 2048
    expand_chunk: int = 8196
    max_head: int = 128_000
    min_head: int = 2048
    need_tail: int = 0

    @classmethod
    def from_content_type(  # noqa: C901
        cls,
        content_type: str,
        file_size: int | None = None,
    ) -> FetchPlan:
        """
        Строит план по MIME-типу и размеру файла.

        Args:
            content_type: MIME-тип из заголовков или guess.
            file_size: Размер файла в байтах, если известен.

        Returns:
            FetchPlan: План чтения для данного типа контента.
        """
        # Маленькие файлы качаем целиком
        if file_size and file_size <= 64_000:
            return cls(
                initial_head=file_size,
                max_head=file_size,
                min_head=file_size,
            )

        # AVI: начало с докачкой
        if content_type in ("video/x-msvideo", "video/msvideo"):
            return cls(
                initial_head=8192,
                expand_chunk=4096,
                max_head=256000,
            )

        # MP3: может иметь большой ID3v2 и иногда нужен хвост
        if content_type in ("audio/mpeg", "audio/mp3"):
            return cls(
                initial_head=8192,
                expand_chunk=8192,
                max_head=32_768,
                need_tail=8192,
            )

        # Видео с moov/seekhead в конце.
        # Без хвоста не возможно определить длительность
        if content_type in (
            "audio/ogg",
            "video/ogg",
            "application/ogg",
            "video/ogv",
        ):
            return cls(
                initial_head=8192,
                expand_chunk=8192,
                need_tail=8192,
            )

        # Видео mp4, если потоковое то все параметры записаны вконце
        if content_type == "video/mp4":
            return cls(
                initial_head=8192,
                expand_chunk=8192,
                max_head=65_536,
                need_tail=24_576,
            )

        # WMA: большой начальный кусок
        if content_type in ("audio/x-ms-wma", "audio/wma"):
            return cls(
                initial_head=8192,
                expand_chunk=8192,
            )

        # JPEG
        if content_type == "image/jpeg":
            if file_size:
                # За счёт EXIF+preview информация о размере может быть глубже
                # Кривая: резкий рост до ~10 КБ на маленьких файлах,
                # плавный до ~30 КБ на средних, пологий до 64 КБ на больших.
                # 10 КБ → 2.9 КБ
                # 500 КБ → 17.5 КБ
                # 1024 КБ → 25 КБ
                needed = min(512 + int(24 * (file_size**0.5)), 65536)
            else:
                needed = 8192

            return cls(
                initial_head=needed,
                expand_chunk=needed // 2,
            )

        # GIF/WebP Для оценки длительности анимации нужно >= 3% файла
        if content_type in ("image/gif", "image/webp"):
            needed = (
                max(20_240, (file_size or 0) // 25) if file_size else 20_240
            )
            needed = min(needed, 256_000)
            return cls(
                initial_head=needed,
                expand_chunk=needed,  # Вероятно никогда не будет использовано
                max_head=needed,  # Чтобы не урезалось
            )

        # По умолчанию для видео
        if content_type.startswith("video/"):
            return cls(
                initial_head=8192,
                expand_chunk=8192,
            )

        # По умолчанию
        return cls()


class MediaChunks(BaseModel):
    """Фрагменты файла, доступные парсеру."""

    head: bytes = b""
    tail: bytes = b""
    file_size: int | None = None
    is_complete: bool = False
    fetched_head: int = 0
    fetched_tail: int = 0


class FileMeta(BaseModel):
    """HTTP-метаданные до чтения тела файла."""

    url: str
    content_type: str = ""
    file_name: str = ""
    file_size: int | None = None


# ============================================================================
# [ ] Базовый класс RangeReader
# ============================================================================


class RangeReader(ABC):
    """Базовый интерфейс для чтения файлов по частям."""

    def __init__(
        self,
        plan: FetchPlan,
        content_type: str,
        file_name: str,
        file_size: int | None,
    ):
        self.plan = plan
        self.content_type = content_type
        self.file_name = file_name
        self.file_size = file_size
        self.head: bytes = b""
        self.tail: bytes = b""

    @abstractmethod
    def __aiter__(self) -> AsyncIterator[MediaChunks]: ...

    @abstractmethod
    async def close(self): ...

    def _make_chunks(self) -> MediaChunks:
        is_complete = (
            self.file_size is not None
            and len(self.head) + len(self.tail) >= self.file_size
        )
        return MediaChunks(
            head=self.head,
            tail=self.tail,
            file_size=self.file_size,
            is_complete=is_complete,
            fetched_head=len(self.head),
            fetched_tail=len(self.tail),
        )


# ============================================================================
# [ ] RangeFileReader
# ============================================================================


class RangeFileReader(RangeReader):
    """Читает локальный файл: head, tail через seek, expand."""

    def __init__(
        self,
        path: str,
        *,
        full_read_limit: int = 20_971_520,  # 20 Мб
    ):
        self.path = path
        file_path = Path(path)

        file_name = file_path.name
        file_size = file_path.stat().st_size
        content_type, _ = mimetypes.guess_type(path)
        content_type = content_type or "application/octet-stream"

        if file_size < full_read_limit:
            # Небольшие данные будем анализировать целиком
            plan = FetchPlan(
                initial_head=file_size,
                expand_chunk=0,
                max_head=file_size,
                need_tail=0,
            )
        else:
            plan = FetchPlan.from_content_type(content_type, file_size)
        logger.debug(
            "FILE plan: initial=%s, expand=%s, tail=%s",
            plan.initial_head,
            plan.expand_chunk,
            plan.need_tail,
        )
        super().__init__(plan, content_type, file_name, file_size)

    async def __aiter__(self) -> AsyncIterator[MediaChunks]:
        # 1. Tail
        if self.plan.need_tail > 0:
            async with await anyio.open_file(self.path, "rb") as f:
                await f.seek(
                    max(0, (self.file_size or 0) - self.plan.need_tail)
                )
                self.tail = await f.read()
            yield self._make_chunks()

        # 2. Head + expand
        async with await anyio.open_file(self.path, "rb") as f:
            # Первый чанк
            self.head = await f.read(self.plan.initial_head)
            logger.debug(
                "head len=%s, tail len=%s", len(self.head), len(self.tail)
            )
            yield self._make_chunks()

            # Докачка
            while (
                self.plan.expand_chunk > 0
                and len(self.head) < self.plan.max_head
            ):
                chunk = await f.read(self.plan.expand_chunk)
                if not chunk:
                    break
                self.head += chunk
                yield self._make_chunks()

    async def close(self):
        pass  # anyio.open_file закрывается через async with


# ============================================================================
# [ ] RangeBytesReader
# ============================================================================


class RangeBytesReader(RangeReader):
    """Читает из bytes/BytesIO без сети."""

    def __init__(
        self,
        data: bytes | BytesIO | NamedBytesIO,
        file_name: str = "",
        *,
        full_read_limit=20_971_520,  # 20 Мб
    ):
        if isinstance(data, (BytesIO, NamedBytesIO)):
            self._file_name = file_name or getattr(data, "name", "")
            raw = data.getbuffer()  # memoryview без копирования
        else:
            self._file_name = file_name
            raw = memoryview(data)  # bytes → memoryview

        self._file_size = len(raw)
        content_type, _ = mimetypes.guess_type(self._file_name)
        content_type = content_type or "application/octet-stream"

        if self._file_size < full_read_limit:
            # Небольшие данные будем анализировать целиком
            plan = FetchPlan(
                initial_head=self._file_size,
                expand_chunk=0,
                max_head=self._file_size,
                need_tail=0,
            )
        else:
            plan = FetchPlan.from_content_type(content_type, self._file_size)
        logger.debug(
            "BYTES plan: initial=%s, expand=%s, tail=%s",
            plan.initial_head,
            plan.expand_chunk,
            plan.need_tail,
        )
        super().__init__(plan, content_type, self._file_name, self._file_size)
        self._raw = raw

    async def __aiter__(self) -> AsyncIterator[MediaChunks]:
        # 1. Tail
        if self.plan.need_tail > 0:
            tail_start = max(0, self._file_size - self.plan.need_tail)
            self.tail = bytes(self._raw[tail_start:])
            yield self._make_chunks()

        # 2. Head + expand (синхронно, без await)
        pos = 0
        while pos < self._file_size:
            chunk_size = (
                self.plan.expand_chunk if pos > 0 else self.plan.initial_head
            )
            if chunk_size <= 0:
                break

            end = min(pos + chunk_size, self._file_size)
            self.head = bytes(self._raw[:end])
            pos = end
            logger.debug(
                "head len=%s, tail len=%s", len(self.head), len(self.tail)
            )

            yield self._make_chunks()

            if end >= self._file_size:
                break

    async def close(self):
        pass


# ============================================================================
# [ ] RangeDownloader (HTTP)
# ============================================================================


class RangeDownloader(RangeReader):
    """
    Самодостаточный загрузчик: определяет тип файла, планирует стратегию,
    скачивает данные не разрывая соединение.

    Использование:
        async with RangeDownloader(url, session=session) as downloader:
            async for chunks in downloader:
                if has_enough(chunks):
                    await downloader.success()
                    break
    """

    def __init__(
        self,
        url: str,
        *,
        session: aiohttp.ClientSession | None = None,
        headers: dict | None = None,
        max_total: int = 256_000,
        timeout: float = 30,
        sock_connect: int = 5,
        max_retries: int = 3,
        retry_on_statuses: tuple[int, ...] = DEFAULT_RETRY_STATUSES,
        retry_backoff_factor: float = 1.0,
    ):
        super().__init__(
            plan=FetchPlan(),
            content_type="",
            file_name="",
            file_size=None,
        )
        self.original_url = url
        self.max_total = max_total

        # Параметры соединения
        self.timeout = ClientTimeout(total=timeout, sock_connect=sock_connect)
        self.max_retries = max_retries
        self.retry_on_statuses = retry_on_statuses
        self.retry_backoff_factor = retry_backoff_factor

        # Сессия
        self._own_session = session is None
        self.session = session

        # Заголовки
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Encoding": "identity",
        }
        if headers:
            self.headers.update(headers)

        # Состояние
        self._response: ClientResponse | None = None
        self._closed: bool = False
        self._fetched_meta: bool = False
        self._meta: FileMeta | None = None
        self._expand_count = 0

    @property
    def final_url(self) -> str:
        return self._meta.url if self._meta else self.original_url

    # ========================================================================
    # Async Context Manager
    # ========================================================================

    async def __aenter__(self):
        if self._own_session:
            self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, *args):
        await self.close()
        if self._own_session and self.session:
            await self.session.close()
            self.session = None

    # ========================================================================
    # Итерация по чанкам
    # ========================================================================

    async def __aiter__(self) -> AsyncIterator[MediaChunks]:
        if self._closed:
            return

        # Получаем метаинформацию и строим план
        if not self._fetched_meta:
            await self._fetch_meta()
            self._meta = cast(FileMeta, self._meta)
            self.content_type = self._meta.content_type
            self.file_name = self._meta.file_name
            self.file_size = self._meta.file_size
            self.plan = FetchPlan.from_content_type(
                self._meta.content_type,
                self._meta.file_size,
            )
            self._fetched_meta = True
            logger.debug(
                "URL plan: initial_head=%s, expand=%s, tail=%s, max=%s",
                self.plan.initial_head,
                self.plan.expand_chunk,
                self.plan.need_tail,
                self.plan.max_head,
            )

        # 1. Tail
        if self.plan.need_tail > 0:
            self.tail = await self._fetch_chunk(
                self.plan.need_tail,
                tail=True,
            )
            yield self._make_chunks()

        # 2. Head
        if self.plan.initial_head > 0:
            self.head = await self._fetch_chunk(
                self.plan.initial_head,
                tail=False,
            )
            yield self._make_chunks()

        # 3. Докачка
        self._expand_count = 0  # Сброс перед докачкой
        while (
            self.plan.expand_chunk > 0 and len(self.head) < self.plan.max_head
        ):
            chunk = await self._expand_head()
            if not chunk:
                break
            self.head += chunk
            yield self._make_chunks()

    # ========================================================================
    # Управление
    # ========================================================================

    async def close(self):
        if not self._closed:
            if self._response:
                self._response.release()
                self._response = None
            self._closed = True

    # ========================================================================
    # Private: Meta
    # ========================================================================

    async def _fetch_meta(self):
        """Получает метаинформацию с retry."""
        response = await self._request_with_retry(self.original_url)
        async with response:
            final_url = str(response.url)
            http_headers = response.headers
            content_type = http_headers.get("Content-Type", "")
            file_name = self._extract_filename(http_headers, self.original_url)

            try:
                file_size = (
                    int(http_headers.get("Content-Length", "0")) or None
                )
            except ValueError:
                file_size = None

            self._meta = FileMeta(
                url=final_url,
                content_type=content_type,
                file_name=file_name,
                file_size=file_size,
            )

    # ========================================================================
    # Private: Fetch with retry
    # ========================================================================

    async def _fetch_chunk(
        self,
        size: int,
        *,
        tail: bool = False,
    ) -> bytes:
        """
        Читает head или tail с retry и циклом до нужного размера.

        Args:
            size: сколько байт читать.
            tail: True — Range-запрос с конца, False — начало файла.
        """
        if not self._meta:
            raise RuntimeError("Метаинформация не загружена.")

        response = await self._request_with_retry(
            self._meta.url,
            allow_range=tail,
            range_bytes=size if tail else None,
        )

        if tail:
            async with response:
                if response.status not in (200, 206):
                    logger.debug(
                        "Range не поддерживается: %s", response.status
                    )
                    return b""
                return await self._read_response(response, size)
        else:
            # Head: сохраняем соединение для докачки
            self._response = response
            data = await self._read_response(response, size)

            # Проверка: если tail повторяет начало head,
            # то Range не поддерживается
            if (
                self.tail
                and len(data) >= len(self.tail)
                and data[: len(self.tail)] == self.tail
            ):
                logger.debug("Range не поддерживается: tail == head")
                self.tail = b""

            logger.debug(
                "Скачан %s: %s байт", "tail" if tail else "head", len(data)
            )

            return data

    async def _read_response(
        self, response: ClientResponse, size: int
    ) -> bytes:
        actual = min(size, self.max_total)
        data = b""
        while len(data) < actual:
            chunk = await response.content.read(actual - len(data))
            if not chunk:
                break
            data += chunk
        return data

    async def _expand_head(self) -> bytes:
        """Докачивает дополнительный кусок к head с удвоением размера."""
        if not self._response or getattr(self._response, "closed", False):
            return b""

        allowed = self.max_total - len(self.head) - len(self.tail)
        if allowed <= 0:
            return b""

        # Удвоение от начального expand_chunk
        chunk_size = min(
            self.plan.expand_chunk * (2**self._expand_count),
            allowed,
        )
        self._expand_count += 1

        try:
            chunk = await self._response.content.read(chunk_size)
            if chunk:
                logger.debug("Докачано: %s байт", len(chunk))
            return chunk
        except Exception:
            return b""

    async def _request_with_retry(
        self,
        url: str,
        *,
        allow_range: bool = False,
        range_bytes: int | None = None,
    ) -> ClientResponse:
        """GET-запрос с retry при серверных ошибках."""
        if not self.session:
            raise RuntimeError(
                "Сессия не установлена. "
                "Используйте async with RangeDownloader(...)"
            )
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                headers = dict(self.headers)
                if allow_range and range_bytes:
                    headers["Range"] = f"bytes=-{range_bytes}"

                response = await self.session.get(url, headers=headers)
            except ClientConnectionError as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.retry_backoff_factor * (2**attempt)
                    logger.debug(
                        "Retry %s/%s через %.1fс для %s (connection error)",
                        attempt + 1,
                        self.max_retries,
                        delay,
                        url,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

            # Серверные ошибки — retry
            if response.status in self.retry_on_statuses:
                response.release()
                if attempt < self.max_retries:
                    delay = self.retry_backoff_factor * (2**attempt)
                    logger.debug(
                        "Retry %s/%s через %.1fс для %s (HTTP %s)",
                        attempt + 1,
                        self.max_retries,
                        delay,
                        url,
                        response.status,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise aiohttp.ClientResponseError(
                    status=response.status,
                    message=(
                        f"Server error after {self.max_retries} "
                        f"retries: HTTP {response.status}"
                    ),
                    headers={},  # type: ignore
                    request_info=response.request_info,
                    history=(),
                )

            # Клиентские ошибки — не retry
            if not response.ok:
                response.release()
                raise aiohttp.ClientResponseError(
                    status=response.status,
                    message=f"HTTP {response.status}",
                    headers=response.headers,
                    request_info=response.request_info,
                    history=response.history,
                )

            return response

        raise last_exception  # type: ignore

    # ========================================================================
    # Private: Helpers
    # ========================================================================

    @staticmethod
    def _extract_filename(
        headers: dict[str, Any] | CIMultiDictProxy[str],
        url: str,
    ) -> str:
        """Извлекает имя файла из Content-Disposition или URL."""
        disp = headers.get("Content-Disposition", "")
        if "filename=" in disp:
            for part in disp.split(";"):
                p = part.strip()
                if p.startswith("filename="):
                    name = p.split("=", 1)[1].strip("\"'")
                    return unquote(name)

        path = urlparse(url).path
        name = path.rstrip("/").rsplit("/", 1)[-1]
        return unquote(name) or "unknown"


# -----------------------------------------------------------------------------
# [ ] FileInspector
# -----------------------------------------------------------------------------


class FileInspector:
    """
    Высокоуровневая обёртка: получает части файла и парсит метаданные
    в FileInfo.

    Поддерживает три источника:
    1. URL — скачивает по HTTP через RangeDownloader.
    2. Локальный файл — читает через RangeFileReader.
    3. bytes/BytesIO — читает через RangeBytesReader.

    Использование:
        inspector = FileInspector()
        info = await inspector.inspect_url("https://example.com/video.mp4",
                                            session=session)
        info = await inspector.inspect_file("/path/to/video.mp4")
        info = await inspector.inspect_bytes(downloaded_bytes)
    """

    def __init__(self):
        self._last_reader: RangeReader | None = None
        self.last_file_info: FileInfo | None = None

    @property
    def last_head(self) -> bytes:
        """Байты head последней инспекции."""

        return self._last_reader.head if self._last_reader else b""

    @property
    def last_tail(self) -> bytes:
        """Байты tail последней инспекции."""

        return self._last_reader.tail if self._last_reader else b""

    # ========================================================================
    # Публичные методы
    # ========================================================================
    async def inspect_url(
        self,
        url: str,
        *,
        session: aiohttp.ClientSession | None = None,
        timeout: int = 30,  # noqa: ASYNC109
        max_total: int = 256_000,
        max_retries: int = 3,
        retry_on_statuses: tuple[int, ...] = DEFAULT_RETRY_STATUSES,
        retry_backoff_factor: float = 1.0,
    ) -> FileInfo:
        """
        Инспектирует удалённый файл по URL.

        Args:
            url: URL файла.
            session: Общая aiohttp-сессия (создаётся при ``None``).
            timeout: Таймаут HTTP-запроса в секундах.
            max_total: Максимальный объём скачанных данных (байт).
            max_retries: Число повторных попыток при ``retry_on_statuses``.
            retry_on_statuses: HTTP-статусы, при которых повторять запрос.
            retry_backoff_factor: Множитель задержки между попытками
                (1.0 → 1с, 2с, 4с).

        Returns:
            FileInfo: Результат инспекции (в т.ч. при сетевой ошибке).
        """

        try:
            async with RangeDownloader(
                url,
                session=session,
                timeout=timeout,
                max_total=max_total,
                max_retries=max_retries,
                retry_on_statuses=retry_on_statuses,
                retry_backoff_factor=retry_backoff_factor,
            ) as reader:
                return await self._inspect(reader, url=url)
        except aiohttp.ClientError as e:
            logger.error("Сетевая ошибка: %s", e)
            self.last_file_info = self._build_file_info(
                url=url,
                error_desc=f"Сетевая ошибка: {e}",
            )
            return self.last_file_info
        except Exception as e:
            logger.exception("Ошибка инспекции: %s", e)
            self.last_file_info = self._build_file_info(
                url=url,
                error_desc=str(e),
            )
            return self.last_file_info

    async def inspect_file(
        self,
        path: str,
        *,
        full_read_limit: int = 20_971_520,  # 20 Мб
    ) -> FileInfo:
        """
        Инспектирует локальный файл.

        Args:
            path: Путь к файлу.
            full_read_limit: Файлы меньше этого размера читаются целиком.

        Returns:
            FileInfo: Результат инспекции.
        """
        try:
            file_path = anyio.Path(path)
            if not await file_path.exists():
                self.last_file_info = self._build_file_info(
                    url=path,
                    error_desc="Файл не найден",
                )
                return self.last_file_info
            reader = RangeFileReader(
                str(await file_path.resolve()), full_read_limit=full_read_limit
            )
            return await self._inspect(reader, url=path)
        except Exception as e:
            logger.exception("Ошибка инспекции файла: %s", e)
            self.last_file_info = self._build_file_info(
                url=path,
                error_desc=str(e),
            )
            return self.last_file_info

    async def inspect_bytes(
        self,
        data: bytes | BytesIO,
        *,
        file_name: str = "",
        full_read_limit: int = 20_971_520,  # 20 Мб
    ) -> FileInfo:
        """
        Инспектирует уже загруженные байты.

        Args:
            data: Содержимое файла.
            file_name: Имя файла (для guess MIME по расширению).
            full_read_limit: Буферы меньше этого размера читаются целиком.

        Returns:
            FileInfo: Результат инспекции.
        """
        if isinstance(data, BytesIO):
            file_name = file_name or getattr(data, "name", "")

        reader = RangeBytesReader(
            data, file_name, full_read_limit=full_read_limit
        )
        return await self._inspect(reader, url="")

    # ========================================================================
    # Private: общая логика инспекции
    # ========================================================================

    async def _inspect(
        self,
        reader: RangeReader,
        *,
        url: str,
    ) -> FileInfo:
        """Общая логика для любого источника (RangeReader)."""
        self._last_reader = reader
        dims = {}
        async for chunks in reader:
            # Проверка: не HTML
            if self._looks_like_html(chunks.head, reader.content_type):
                self.last_file_info = self._build_file_info(
                    url=url,
                    mime_type=reader.content_type,
                    file_name=reader.file_name,
                    file_size=reader.file_size,
                    error_desc="Файл не является медиа (HTML-страница)",
                )
                return self.last_file_info

            # Парсим
            dims = (
                self.parse_media_dimensions(
                    chunks.head,
                    chunks.tail,
                    reader.content_type,
                    reader.file_size,
                )
                or {}
            )

            # Уточняем content_type если octet-stream
            content_type = reader.content_type
            fmt = dims.get("format")
            if (
                fmt
                and _FORMAT_TO_MIME.get(fmt)
                and (
                    not content_type
                    or content_type == "application/octet-stream"
                )
            ):
                content_type = _FORMAT_TO_MIME[fmt]

            # Достаточно ли данных
            if self._is_complete(dims, content_type):
                logger.debug(
                    "Использовано финально head_len=%s, tail_len=%s",
                    len(chunks.head),
                    len(chunks.tail),
                )

                self.last_file_info = self._build_file_info(
                    url=url,
                    mime_type=content_type,
                    file_name=reader.file_name,
                    file_size=reader.file_size,
                    dims=dims,
                )
                return self.last_file_info

        # Цикл кончился — не хватило данных
        self.last_file_info = self._build_file_info(
            url=url,
            mime_type=reader.content_type,
            file_name=reader.file_name,
            file_size=reader.file_size,
            dims=dims or None,
            error_desc="Недостаточно данных для определения параметров",
        )
        return self.last_file_info

    # ========================================================================
    # Private: хелперы
    # ========================================================================

    @staticmethod
    def _looks_like_html(head: bytes, content_type: str) -> bool:
        """Определяет, похож ли ответ на HTML-страницу."""
        if content_type.startswith("text/html"):
            return True
        if len(head) < 16:
            return False
        head_lower = head[:512].lower().lstrip()
        return head_lower.startswith((b"<!doctype html", b"<html"))

    @staticmethod
    def _is_complete(dims: dict, content_type: str) -> bool:
        """Проверяет, достаточно ли данных для этого типа контента."""
        if not dims:
            return False
        if content_type.startswith("image/"):
            return bool(dims.get("width") and dims.get("height"))
        if content_type.startswith("audio/"):
            return bool(dims.get("duration") and dims.get("sample_rate"))
        if content_type.startswith("video/"):
            if dims.get("error_desc") == (
                "Для определения duration необходим "
                "конец файла (tail) или файл целиком"
            ):
                return True
            return bool(
                dims.get("duration") and dims.get("width") and dims.get("fps")
            )
        return bool(dims)

    @staticmethod
    def _build_file_info(
        url: str = "",
        mime_type: str = "",
        file_name: str = "",
        file_size: int | None = None,
        dims: dict | None = None,
        error_desc: str = "",
    ) -> FileInfo:
        """Собирает FileInfo из параметров."""
        if dims is None:
            dims = {}

        # Вычисляем производные поля
        bitrate_avg = None
        if file_size and dims.get("duration"):
            bitrate_avg = round(file_size / dims["duration"] * 8 / 1024)

        duration = dims.get("duration")
        if duration is not None:
            duration = round(duration, 1) if duration < 10 else round(duration)

        return FileInfo(
            url=url,
            mime_type=mime_type,
            file_name=file_name,
            file_size=file_size,
            width=dims.get("width"),
            height=dims.get("height"),
            format=dims.get("format"),
            duration=duration,
            fps=dims.get("fps"),
            sample_rate=dims.get("sample_rate"),
            bitrate_nominal=dims.get("bitrate_nominal") or dims.get("bitrate"),
            bitrate_avg=bitrate_avg,
            error_desc=error_desc or dims.get("error_desc", ""),
        )

    @classmethod
    def parse_media_dimensions(
        cls,
        head: bytes,
        tail: bytes | None,
        content_type: str | None = None,
        file_size: int | None = None,
    ) -> dict | None:
        """
        Извлекает метаданные из фрагментов файла.

        Args:
            head: Байты с начала файла.
            tail: Байты с конца (если нужны для формата).
            content_type: MIME-тип, опционально
            file_size: Полный размер файла, если известен.

        Returns:
            Словарь полей для :class:`FileInfo` или ``None``.
        """
        if len(head) < 2:
            return None

        if not content_type or content_type == "application/octet-stream":
            # Если сервер не определил тип файла
            # Проверим все типы по содержанию
            result = cls._parse_image_dimensions(head, content_type, file_size)
            if result:
                return result
            result = cls._parse_video_dimensions(
                head, tail, content_type, file_size
            )
            if result:
                return result
            result = cls._parse_audio_dimensions(
                head, tail, content_type, file_size
            )
            if result:
                return result

        if content_type.startswith("image/"):
            return cls._parse_image_dimensions(head, content_type, file_size)

        if content_type.startswith("video/"):
            return cls._parse_video_dimensions(
                head, tail, content_type, file_size
            )

        if content_type.startswith("audio/"):
            return cls._parse_audio_dimensions(
                head, tail, content_type, file_size
            )

        return None

    @classmethod
    def _parse_image_dimensions(
        cls, data: bytes, content_type: str, file_size: int | None
    ) -> dict | None:
        """
        Парсит метаданные изображений, определяя формат по сигнатурам,
        с fallback на content_type.

        Args:
            data: начальные байты файла (head).
            content_type: MIME-тип из заголовков HTTP.
            file_size: размер файла в байтах (опционально).

        Returns:
            dict с ключами format, width, height или None.
        """

        # WEBP — сигнатура RIFF WEBP
        if cls._webp_check(data):
            return cls._webp_parse(data, file_size)

        # PNG — сигнатура 8 байт + IHDR
        if cls._png_check(data):
            return cls._png_parse(data)

        # JPEG — сигнатура \xFF\xD8
        if cls._jpg_check(data):
            return cls._jpeg_parse(data)

        # GIF — сигнатура GIF87a / GIF89a
        if cls._gif_check(data):
            return cls._gif_parse_info(data, file_size)

        # Fallback на content_type, если байты не распознаны
        # Это полезно, если файл обрезан или сигнатура нестандартна
        if content_type == "image/webp":
            return cls._webp_parse(data, file_size)
        if content_type == "image/png":
            return cls._png_parse(data)
        if content_type == "image/jpeg":
            return cls._jpeg_parse(data)
        if content_type == "image/gif":
            return cls._gif_parse_info(data, file_size)

        return None

    @classmethod
    def _parse_video_dimensions(  # noqa: C901
        cls,
        head: bytes,
        tail: bytes | None,
        content_type: str,
        file_size: int | None,
    ) -> dict | None:
        """
        Парсит метаданные видео, определяя формат по сигнатурам,
        с fallback на content_type.

        Args:
            head: начальные байты файла.
            tail: конечные байты файла (опционально, для moov/seekhead).
            content_type: MIME-тип из заголовков HTTP.
            file_size: размер файла в байтах (опционально).

        Returns:
            dict с ключами format, width, height, fps, duration или None.
        """

        # MP4 / MOV — сигнатура ftyp или moov
        if cls._mp4_check(head):
            return cls._mp4_parse_info(head, tail)

        # AVI — сигнатура RIFF AVI
        if cls._avi_check(head):
            return cls._avi_parse_info(head)

        # MKV / WebM — сигнатура EBML
        if cls._webm_mkv_check(head):
            result = cls._webm_mkv_parse_info(head)
            # format определяется по содержанию,
            # но если есть content_type, берём из него.
            if content_type:
                if not result:
                    result = {}
                if content_type == "video/webm":
                    result["format"] = "WEBM"
                elif content_type == "video/x-matroska":
                    result["format"] = "MKV"
            return result

        # OGV / OGG — сигнатура OggS
        if cls._ogg_ogv_check(head):
            return cls._ogg_parse_info(head, tail, file_size)

        # Fallback на content_type, если байты не распознаны
        # Это полезно, если файл обрезан или сигнатура нестандартна
        if content_type in ("video/mp4", "video/quicktime"):
            return cls._mp4_parse_info(head)
        if content_type in ("video/x-msvideo", "video/msvideo"):
            return cls._avi_parse_info(head)
        if content_type == "video/webm":
            result = cls._webm_mkv_parse_info(head)
            if result:
                result["format"] = "WEBM"
            return result
        if content_type == "video/x-matroska":
            result = cls._webm_mkv_parse_info(head)
            if result:
                result["format"] = "MKV"
            return result
        if content_type in ("video/ogg", "application/ogg", "video/ogv"):
            return cls._ogg_parse_info(head, tail, file_size)

        return None

    @classmethod
    def _parse_audio_dimensions(  # noqa: C901
        cls,
        head: bytes,
        tail: bytes | None,
        content_type: str,
        file_size: int | None,
    ) -> dict | None:
        """
        Парсит метаданные аудио, определяя формат по сигнатурам,
        с fallback на content_type.

        Args:
            head: начальные байты файла.
            tail: конечные байты файла (опционально, для Vorbis/Opus).
            content_type: MIME-тип из заголовков HTTP.
            file_size: размер файла в байтах (опционально).

        Returns:
            dict с ключами format, duration, sample_rate, bitrate или None.
        """

        if cls._mp3_check(head):
            return cls._mp3_parse_info(head, tail, file_size)

        # WAV (RIFF WAVE)
        if cls._wav_check(head):
            return cls._wav_parse_info(head)

        # FLAC (fLaC)
        if cls._flac_check(head):
            return cls._flac_parse_info(head)

        # OGG / OPUS / SPEEX (OggS)
        if cls._ogg_ogv_check(head):
            return cls._ogg_parse_info(head, tail, file_size)

        # AAC (ADTS)
        if cls._aac_check(head):
            return cls._aac_parse_info(head, file_size)

        # M4A (ftyp)
        if cls._m4a_check(head):
            return cls._m4a_parse_audio_info(head)

        # WMA / ASF
        if cls._wma_check(head):
            return cls._wma_parse_info(head)

        # Fallback на content_type, если байты не распознаны
        # Это полезно, если файл обрезан или сигнатура нестандартна
        if content_type in ("audio/mpeg", "audio/mp3"):
            return cls._mp3_parse_info(head, tail, file_size)
        if content_type == "audio/mp4":
            return cls._m4a_parse_audio_info(head)
        if content_type in ("audio/ogg", "application/ogg"):
            return cls._ogg_parse_info(head, tail, file_size)
        if content_type in ("audio/aac", "audio/x-aac"):
            return cls._aac_parse_info(head, file_size)
        if content_type in ("audio/wav", "audio/x-wav", "audio/wave"):
            return cls._wav_parse_info(head)
        if content_type in ("audio/x-ms-wma", "audio/wma"):
            return cls._wma_parse_info(head)

        return None

    # =========================================================================
    # [ ] Методы определения формата по сигнатуре
    # =========================================================================

    # --- image ---
    @staticmethod
    def _png_check(data: bytes) -> bool:
        return (
            len(data) >= 24
            and data[:8] == b"\x89PNG\r\n\x1a\n"
            and data[12:16] == b"IHDR"
        )

    @staticmethod
    def _webp_check(data: bytes) -> bool:
        return len(data) >= 12 and data[8:12] == b"WEBP"

    @staticmethod
    def _jpg_check(data: bytes) -> bool:
        return len(data) > 2 and data[:2] == b"\xff\xd8"

    @staticmethod
    def _gif_check(data: bytes) -> bool:
        return len(data) >= 10 and data[:6] in (b"GIF87a", b"GIF89a")

    # --- audio ---
    @staticmethod
    def _mp3_check(data: bytes) -> bool:
        return data.startswith(b"ID3") or (  # MP3 (ID3v2)
            # MP3 (без тегов, начинается с фрейма sync word 0xFFE0)
            len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xFE) == 0xE0
        )

    @staticmethod
    def _wav_check(data: bytes) -> bool:
        return (
            len(data) >= 12
            and data.startswith(b"RIFF")
            and data[8:12] == b"WAVE"
        )

    @staticmethod
    def _flac_check(data: bytes) -> bool:
        return data.startswith(b"fLaC")

    @staticmethod
    def _ogg_ogv_check(data: bytes) -> bool:
        # Для Ogg нужно проверить тип потока внутри (Opus, Vorbis и т.д.)
        # Обычно это делается через _ogg_parse_info, который смотрит внутрь
        return data.startswith(b"OggS")

    @staticmethod
    def _aac_check(data: bytes) -> bool:
        return len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xF6) == 0xF0

    @staticmethod
    def _m4a_check(data: bytes) -> bool:
        """Определяет, является ли MP4-файл аудио (M4A) по бренду."""
        if len(data) >= 12 and data[4:8] == b"ftyp":
            brand = data[8:12]
            return brand in (b"M4A ", b"M4B ", b"M4P ", b"F4A ", b"F4B ")
        return False

    @staticmethod
    def _wma_check(data: bytes) -> bool:
        return data.startswith(
            b"\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\x00\xaa\x00\x62\xce\x6c"
        )

    # --- video ---
    @staticmethod
    def _mp4_check(data: bytes) -> bool:
        """MP4/MOV/M4A — ftyp или сразу moov/mdat (старый QuickTime)."""
        if len(data) < 4:
            return False
        if data[4:8] == b"ftyp":
            brand = data[8:12]
            # Явно видео бренды или общие (isom может быть и аудио)
            # fmt: off
            return brand in {
                b"mp42", b"isom", b"iso2", b"avc1", b"mp41", b"iso5",
                b"iso6", b"msnv", b"ndsc", b"ndsh", b"ndsm", b"ndsp",
                b"ndss", b"ndxc", b"ndxh", b"ndxm", b"ndxp", b"ndxs"}
        # Старый QuickTime: начинается с moov или mdat
        return data[0:4] in (b"moov", b"mdat", b"wide", b"skip", b"free")

    @staticmethod
    def _avi_check(data: bytes) -> bool:
        return len(data) > 8 and data[0:4] == b"RIFF" and data[8:12] == b"AVI "

    @staticmethod
    def _webm_mkv_check(data: bytes) -> bool:
        return len(data) > 3 and data[1:4] == b"\x45\xdf\xa3"

    # =========================================================================
    # [ ] Парсеры: изображения
    # =========================================================================

    @classmethod
    def _png_parse(cls, data: bytes) -> dict[str, Any] | None:
        if not cls._png_check(data):
            return
        w, h = struct.unpack(">II", data[16:24])
        return {"width": w, "height": h, "format": "PNG"}

    @staticmethod
    def _webp_parse(  # noqa: C901
        data: bytes, file_size: int | None = None
    ) -> dict[str, Any] | None:
        """
        Парсит метаданные из WEBP-файла.

        Поддерживает форматы:
        - WEBP/VP8X (расширенный, с анимацией/альфа-каналом)
        - WEBP/VP8 (стандартный lossy)
        - WEBP/VP8L (lossless)

        Args:
            data: Начальные байты файла
                (рекомендуется ≥ 32 КБ для анимированных)
            file_size: Полный размер файла в байтах (опционально,
                для апроксимации длительности)

        Returns:
            dict с ключами: format, width, height, duration, fps
            None, если формат не распознан
        """
        # Базовая проверка заголовка RIFF WEBP
        if len(data) < 12 or data[0:4] != b"RIFF" or data[8:12] != b"WEBP":
            return None

        result: dict[str, Any] = {"format": "WEBP"}

        # Переменные для накопления данных об анимации
        total_ms = 0
        frame_count = 0

        pos = 12
        while pos + 8 <= len(data):
            chunk_type = data[pos : pos + 4]
            chunk_size = struct.unpack("<I", data[pos + 4 : pos + 8])[0]

            # Проверка границ данных чанка
            payload_start = pos + 8
            payload_end = payload_start + chunk_size

            # Если чанк обрезан, прерываемся (но сохраняем то, что нашли)
            is_chunk_complete = payload_end <= len(data)

            # --- Обработка конкретных чанков ---

            # 1. VP8X: Расширенный формат (флаги, размеры canvas)
            if chunk_type == b"VP8X" and len(data) >= payload_start + 10:
                # Размеры в VP8X хранятся как (value - 1)
                width = (
                    int.from_bytes(
                        data[payload_start + 4 : payload_start + 7], "little"
                    )
                    + 1
                )
                height = (
                    int.from_bytes(
                        data[payload_start + 7 : payload_start + 10], "little"
                    )
                    + 1
                )
                result.update(
                    {"width": width, "height": height, "format": "WEBP/VP8X"}
                )

            # 2. ANMF: Кадр анимации (только если чанк полный)
            elif (
                chunk_type == b"ANMF"
                and is_chunk_complete
                and chunk_size >= 16
            ):
                frame_count += 1
                # Длительность кадра:
                # 3 байта little-endian по смещению 12 от начала payload
                dur_offset = payload_start + 12
                duration_raw = int.from_bytes(
                    data[dur_offset : dur_offset + 3], "little"
                )

                # Конвертация длительности WEBP (ms * 1000 / 1001) обратно в мс
                # Если 0, то по спецификации это часто
                # интерпретируется как 100мс
                duration_ms = (
                    round(duration_raw * 1001 / 1000)
                    if duration_raw > 0
                    else 100
                )
                total_ms += duration_ms

            # 3. VP8 : Lossy изображение (первый кадр или статика)
            elif chunk_type == b"VP8 " and len(data) >= payload_start + 30:
                # Проверяем, что это ключевой кадр (frame tag)
                # Frame tag находится в начале payload.
                # Если бит 0 равен 0, это key frame.
                if payload_start + 10 <= len(data):
                    frame_tag = data[payload_start]
                    if (frame_tag & 0x01) == 0:
                        width = (
                            struct.unpack(
                                "<H",
                                data[payload_start + 6 : payload_start + 8],
                            )[0]
                            & 0x3FFF
                        )
                        height = (
                            struct.unpack(
                                "<H",
                                data[payload_start + 8 : payload_start + 10],
                            )[0]
                            & 0x3FFF
                        )
                        # Обновляем только если еще не нашли размеры
                        # (приоритет у VP8X, если он есть,
                        # но обычно VP8X идет первым. Если VP8X нет,
                        # берем из VP8)
                        if "width" not in result:
                            result.update(
                                {
                                    "width": width,
                                    "height": height,
                                    "format": "WEBP/VP8",
                                }
                            )

            # 4. VP8L: Lossless изображение
            elif (
                chunk_type == b"VP8L" and is_chunk_complete and chunk_size >= 5
            ):
                if payload_start + 4 <= len(data):
                    bits = struct.unpack(
                        "<I", data[payload_start : payload_start + 4]
                    )[0]
                    width = (bits & 0x3FFF) + 1
                    height = ((bits >> 14) & 0x3FFF) + 1
                    if "width" not in result:
                        result.update(
                            {
                                "width": width,
                                "height": height,
                                "format": "WEBP/VP8L",
                            }
                        )

            # Переход к следующему чанку (выравнивание по четному байту)
            next_pos = payload_end
            if next_pos % 2 != 0:
                next_pos += 1

            # Защита от бесконечного цикла при битых данных
            if next_pos <= pos:
                break
            pos = next_pos

        # Если размеры не найдены, файл невалиден для наших целей
        if "width" not in result or "height" not in result:
            return result

        # --- Расчет длительности и FPS ---
        if frame_count > 0:
            result["frames"] = frame_count
            scanned_duration_sec = total_ms / 1000.0

            # Экстраполяция, если файл обрезан (data < file_size)
            if file_size and file_size > len(data) and len(data) > 0:
                ratio = file_size / len(data)
                # Предполагаем равномерное распределение данных
                estimated_duration_sec = scanned_duration_sec * ratio
                result["duration"] = estimated_duration_sec
                if estimated_duration_sec > 0:
                    result["fps"] = round(
                        (frame_count * ratio) / estimated_duration_sec, 3
                    )
                result["error_desc"] = (
                    "Длительность и частота кадров определены "
                    "экстраполирвоанием (приблизительно)"
                )
            else:
                result["duration"] = scanned_duration_sec
                if scanned_duration_sec > 0:
                    result["fps"] = round(
                        frame_count / scanned_duration_sec, 3
                    )

        return result

    @staticmethod
    def _gif_parse_info(
        data: bytes, file_size: int | None = None
    ) -> dict[str, Any]:
        """
        Извлекает метаданные из GIF по заголовку.

        Аргументы:
            data: Первые байты файла (рекомендуется ≥ 20 КБ).
            file_size: Полный размер файла.

        Возвращает:
            dict с 'format', 'width', 'height', 'bitrate' или None.
        """
        if len(data) < 10 or data[:6] not in (b"GIF87a", b"GIF89a"):
            return {}

        # Логические размеры изображения
        width, height = struct.unpack("<HH", data[6:10])

        result: dict[str, Any] = {
            "format": "GIF",
            "width": width,
            "height": height,
        }

        # Подсчёт кадров и длительности
        total_cs = 0
        frame_count = 0
        pos = 0
        while True:
            idx = data.find(b"\x21\xf9\x04", pos)  # Graphic Control Extension
            if idx < 0 or idx + 8 > len(data):
                break
            delay_cs = struct.unpack("<H", data[idx + 4 : idx + 6])[0]
            # GIF: delay в сотых долях секунды,
            # 0 = использовать дефолт (обычно 10)
            if delay_cs == 0:
                delay_cs = 10
            total_cs += delay_cs
            frame_count += 1
            pos = idx + 8

        if frame_count > 0:
            # Длительность по просканированным кадрам
            scanned_duration_sec = total_cs / 100.0

            data_size = len(data)
            # Если известен полный размер файла — экстраполируем
            if file_size and file_size > data_size:
                ratio = file_size / data_size
                result["duration"] = scanned_duration_sec * ratio
                result["error_desc"] = (
                    "Длительность и частота кадров определены "
                    "экстраполирвоанием (приблизительно)"
                )
            else:
                # Файл маленький или размер неизвестен — возвращаем как есть
                result["duration"] = scanned_duration_sec

            # FPS считаем по просканированным кадрам
            if scanned_duration_sec > 0:
                result["fps"] = round(frame_count / scanned_duration_sec, 3)

        return result

    @staticmethod
    def _jpeg_parse(data: bytes) -> dict | None:
        if len(data) < 2 or data[:2] != b"\xff\xd8":
            return None

        pos = 2
        while pos < len(data) - 1:
            if data[pos] != 0xFF:
                pos += 1
                continue
            marker = data[pos + 1]
            if (
                marker in (0xC0, 0xC1, 0xC2)  # SOF0, SOF1, SOF2
                and pos + 9 <= len(data)
            ):
                h, w = struct.unpack(">HH", data[pos + 5 : pos + 9])
                return {"width": w, "height": h, "format": "JPEG"}
            # Пропускаем сегменты
            if marker not in (1, *tuple(range(208, 218))):
                if pos + 4 <= len(data):
                    segment_length = struct.unpack(
                        ">H", data[pos + 2 : pos + 4]
                    )[0]
                    pos += 2 + segment_length
                else:
                    break
            else:
                pos += 2
        return None

    # =========================================================================
    # [ ] Парсеры: видео
    # =========================================================================

    @classmethod
    def _mp4_parse_info(
        cls, data: bytes, tail: bytes | None = None
    ) -> dict | None:
        """
        Парсит размеры и длительность из MP4/MOV файла.

        Ищет атом moov в head и tail. Для файлов с moov в конце
        (потоковая запись) нужен tail.
        """
        result = None
        if cls._mp4_check(data):
            result = {"format": "MP4"}

        # Ищем moov в head
        dims = cls._mp4_find_moov(data)
        if dims and result:
            result.update(dims)
            return result

        # Ищем moov в tail
        if tail:
            dims = cls._mp4_find_moov(tail)
            if dims and result:
                result.update(dims)
                return result

        return result

    @classmethod
    def _mp4_find_moov(cls, data: bytes) -> dict | None:
        """Ищет атом moov в данных и парсит его."""
        idx = data.find(b"moov")
        if idx < 4:
            return None

        # Размер атома перед moov
        size = struct.unpack(">I", data[idx - 4 : idx])[0]

        # Берём moov — либо полный, либо до конца данных
        moov_start = idx - 4
        moov_end = min(moov_start + size, len(data))
        moov_data = data[moov_start + 8 : moov_end]  # +8 пропускаем size+type

        return cls._mp4_moov_parse(moov_data)

    @classmethod
    def _mp4_moov_parse(cls, data: bytes) -> dict | None:
        result: dict[str, int | float | str] = {}
        pos = 0
        while pos + 8 <= len(data):
            size = struct.unpack(">I", data[pos : pos + 4])[0]
            atom_type = data[pos + 4 : pos + 8]

            if size == 0:
                break
            header_size = 16 if size == 1 else 8
            if size == 1:
                if pos + 16 > len(data):
                    break
                size = struct.unpack(">Q", data[pos + 8 : pos + 16])[0]

            if atom_type == b"mvhd":
                duration = cls._m4a_parse_mvhd_duration(data[pos : pos + size])
                if duration is not None:
                    result["duration"] = duration
                    result["format"] = "MP4"
            elif atom_type == b"trak":
                trak_data = data[pos + header_size : pos + size]
                dims = cls._mp4_parse_trak_for_dims(trak_data)
                if dims and cls._mp4_valid_video_dims(dims):
                    result.update(dims)

            pos += size
            if size < header_size:
                break
        return result or None

    @classmethod
    def _mp4_parse_trak_for_dims(cls, data: bytes) -> dict | None:
        """Ищет tkhd внутри trak"""
        pos = 0
        while pos + 8 <= len(data):
            size = struct.unpack(">I", data[pos : pos + 4])[0]
            atom_type = data[pos + 4 : pos + 8]

            if size == 0:
                break
            if size == 1:
                if pos + 16 > len(data):
                    break
                size = struct.unpack(">Q", data[pos + 8 : pos + 16])[0]
                header_size = 16
            else:
                header_size = 8

            if atom_type == b"tkhd":
                return cls._mp4_parse_tkhd(
                    data[pos + header_size : pos + size]
                )

            pos += size
            if size < header_size:
                break
        return None

    @staticmethod
    def _mp4_parse_tkhd(data: bytes) -> dict | None:
        """Парсит tkhd atom. Версии 0 и 1."""
        if len(data) < 80:  # Минимальный размер для версии 0
            return None

        version = data[0]
        # flags = data[1:4]

        if version == 0:
            # creation_time (4), modification_time (4), track_id (4),
            # reserved (4), duration (4), reserved (8), layer (2),
            # alternate_group (2), volume (2), reserved(2), matrix (36)
            # width (4), height (4)
            # Смещение до width: 4 bytes version/flags + 72 bytes полей = 76
            if len(data) < 84:
                return None
            w_fixed = struct.unpack(">I", data[76:80])[0]
            h_fixed = struct.unpack(">I", data[80:84])[0]
            # Значения в формате 16.16 fixed point
            return {
                "width": w_fixed >> 16,
                "height": h_fixed >> 16,
                "format": "MP4",
            }
        elif version == 1:
            # creation_time (8), modification_time (8), track_id (4),
            # reserved (4), duration (8), reserved (8), layer (2),
            # alternate_group(2), volume(2), reserved (2), matrix (36),
            # width (4), height (4)
            # Смещение c учетом version/flags: 92 байта
            if len(data) < 100:
                return None
            w_fixed = struct.unpack(">I", data[92:96])[0]
            h_fixed = struct.unpack(">I", data[96:100])[0]
            return {
                "width": w_fixed >> 16,
                "height": h_fixed >> 16,
                "format": "MP4",
            }
        return None

    @staticmethod
    def _mp4_valid_video_dims(result: dict | None) -> bool:
        """Проверяет, что размеры видео реалистичны."""
        if not result:
            return False
        w = result.get("width") or 0
        h = result.get("height") or 0
        return (
            # Некоторые файлы имеют 0x40000000 (16384.0) как "не задано"
            not (w == 16_384 and h == 16_384)
            # Минимальное видео — хотя бы 2×2
            and not (w < 2 or h < 2)
            # 16K с запасом на будущее
            and not (w > 16_384 or h > 16_384)
        )

    @classmethod
    def _avi_parse_info(cls, data: bytes) -> dict | None:
        """
        Парсит AVI файл и возвращает словарь с метаинформацией.

        Извлекает параметры видео (ширина, высота, FPS, длительность)
        и аудио (частота дискретизации, битрейт) из RIFF AVI структуры.

        Примечание о битрейте:
        Формат AVI (особенно с кодеками типа M-JPEG, DivX, Xvid) обычно
        использует переменный битрейт (VBR) или не хранит точное значение
        среднего битрейта в заголовке. Поле dwMaxBytesPerSec в главном
        заголовке часто содержит лишь приблизительную оценку или пиковое
        значение, которое не отражает реальный размер файла.

        Args:
            data: сырые байты начала файла (минимум 56 байт для avih)

        Returns:
            dict с ключами width, height, fps, duration, sample_rate,
            bitrate, format
            или None если файл не является корректным AVI
        """
        if len(data) < 12:
            return None

        # Проверка сигнатуры RIFF AVI
        if data[0:4] != b"RIFF" or data[8:12] != b"AVI ":
            return None

        result = {
            "width": None,
            "height": None,
            "fps": None,
            "sample_rate": None,
            "duration": None,
            "bitrate": None,  # Номинальный (из заголовка avih)
            "format": "AVI",
            "total_frames": None,
            "file_size": len(data),  # Размер данных, которые у нас есть
        }

        pos = 12
        end = len(data)

        while pos + 8 <= end:
            chunk_id = data[pos : pos + 4]
            chunk_size = struct.unpack_from("<I", data, pos + 4)[0]

            if chunk_size > end - pos - 8:
                break

            next_pos = pos + 8 + chunk_size
            if chunk_size % 2 != 0:
                next_pos += 1

            if (
                chunk_id == b"LIST"
                and pos + 12 <= end
                and data[pos + 8 : pos + 12] == b"hdrl"
            ):
                cls._parse_hdrl(data, pos + 12, pos + 8 + chunk_size, result)
                break  # hdrl всегда первый, дальше можно не искать

            if next_pos <= pos:
                break
            pos = next_pos

        # Вычисляем длительность
        if result["total_frames"] and result["fps"]:
            result["duration"] = int(result["total_frames"] / result["fps"])

        # Удаляем служебные ключи
        result.pop("total_frames", None)
        result.pop("file_size", None)

        return result

    @classmethod
    def _parse_hdrl(cls, data: bytes, start: int, end: int, result: dict):
        """
        Парсит LIST hdrl, извлекает avih и потоки strl.

        Args:
            data: байты данных
            start, end: границы чанка hdrl
            result: словарь для заполнения (изменяется in-place)
        """
        pos = start
        while pos + 8 <= end:
            chunk_id = data[pos : pos + 4]
            chunk_size = struct.unpack_from("<I", data, pos + 4)[0]

            if chunk_size > end - pos - 8:
                break

            next_pos = pos + 8 + chunk_size
            if chunk_size % 2 != 0:
                next_pos += 1

            chunk_end = min(pos + 8 + chunk_size, end)

            if chunk_id == b"avih":
                cls._parse_avih(data, pos + 8, chunk_end, result)
            elif (
                chunk_id == b"LIST"
                and pos + 12 <= end
                and data[pos + 8 : pos + 12] == b"strl"
            ):
                cls._parse_strl(data, pos + 12, chunk_end, result)

            if next_pos <= pos:
                break
            pos = next_pos

    @staticmethod
    def _parse_avih(data: bytes, start: int, end: int, result: dict):
        """
        Парсит MainAVIHeader (56 байт).

        Структура:
        - dwMicroSecPerFrame (0-3): микросекунд на кадр
        - dwMaxBytesPerSec (4-7): ОБЩИЙ максимальн. битрейт файла (видео+аудио)
        - dwPaddingGranularity (8-11): выравнивание
        - dwFlags (12-15): флаги
        - dwTotalFrames (16-19): общее количество кадров
        - dwInitialFrames (20-23): начальные кадры
        - dwStreams (24-27): количество потоков
        - dwSuggestedBufferSize (28-31): рекомендуемый размер буфера
        - dwWidth (32-35): ширина
        - dwHeight (36-39): высота
        - dwReserved[4] (40-55): зарезервировано
        """
        if end - start < 56:
            return

        # Номинальный битрейт - ОБЩИЙ для всего файла
        max_bytes_per_sec = struct.unpack_from("<I", data, start + 4)[0]
        if max_bytes_per_sec > 0:
            result["bitrate"] = int((max_bytes_per_sec * 8) / 1000)

        # Общее количество кадров
        result["total_frames"] = struct.unpack_from("<I", data, start + 16)[0]

        # Размеры кадра
        width = struct.unpack_from("<I", data, start + 32)[0]
        height = struct.unpack_from("<I", data, start + 36)[0]
        if width > 0:
            result["width"] = width
        if height > 0:
            result["height"] = height

    @classmethod
    def _parse_strl(cls, data: bytes, start: int, end: int, result: dict):
        """
        Парсит LIST strl, ищет strh (заголовок потока) и strf (формат потока).
        """
        pos = start
        while pos + 8 <= end:
            chunk_id = data[pos : pos + 4]
            chunk_size = struct.unpack_from("<I", data, pos + 4)[0]

            if chunk_size > end - pos - 8:
                break

            next_pos = pos + 8 + chunk_size
            if chunk_size % 2 != 0:
                next_pos += 1

            chunk_end = min(pos + 8 + chunk_size, end)

            if chunk_id == b"strh":
                cls._parse_strh(data, pos + 8, chunk_end, result)
            elif chunk_id == b"strf":
                cls._parse_strf(data, pos + 8, chunk_end, result)

            if next_pos <= pos:
                break
            pos = next_pos

    @staticmethod
    def _parse_strh(data: bytes, start: int, end: int, result: dict):
        """
        Парсит AVISTREAMHEADER (56 байт).

        Для видео (vids):
        - dwRate/dwScale = FPS
        - rcFrame = размер кадра

        Для аудио (auds):
        - dwRate = частота дискретизации (предварительно)
        - Более точная частота будет в strf (nSamplesPerSec)
        """
        if end - start < 56:
            return

        stream_type = data[start : start + 4]
        dw_scale = struct.unpack_from("<I", data, start + 20)[0]
        dw_rate = struct.unpack_from("<I", data, start + 24)[0]

        if stream_type == b"vids":
            # Размер кадра (если ещё не определён из avih)
            if result["width"] is None:
                left = struct.unpack_from("<I", data, start + 40)[0]
                top = struct.unpack_from("<I", data, start + 44)[0]
                right = struct.unpack_from("<I", data, start + 48)[0]
                bottom = struct.unpack_from("<I", data, start + 52)[0]

                w = right - left
                h = bottom - top
                if w > 0:
                    result["width"] = w
                if h > 0:
                    result["height"] = h

            # FPS = dwRate / dwScale
            if dw_scale > 0 and dw_rate > 0:
                result["fps"] = round(dw_rate / dw_scale, 2)

        elif stream_type == b"auds":
            # Предварительная частота из strh (может быть неточной)
            # Приоритет будет у strf (nSamplesPerSec)
            if result["sample_rate"] is None and dw_rate > 0:
                # Проверяем, похоже ли на стандартную частоту
                # fmt: off
                standard_rates = {
                    8000, 11025, 12000, 16000, 22050, 24000,
                    32000, 44100, 48000, 88200, 96000, 192000,
                }
                # fmt: on
                if dw_rate in standard_rates:
                    result["sample_rate"] = dw_rate

    @staticmethod
    def _parse_strf(data: bytes, start: int, end: int, result: dict):
        """
        Парсит WAVEFORMATEX (аудио) или BITMAPINFOHEADER (видео).

        Для аудио WAVEFORMATEX (минимум 16 байт):
        - wFormatTag (0-1): тип формата
        - nChannels (2-3): количество каналов
        - nSamplesPerSec (4-7): ЧАСТОТА ДИСКРЕТИЗАЦИИ наиболее точное значение
        - nAvgBytesPerSec (8-11): средний байтрейт ТОЛЬКО аудио потока
        - nBlockAlign (12-13): выравнивание блока
        - wBitsPerSample (14-15): бит на сэмпл (для PCM)
        """
        if end - start < 16:
            return

        format_tag = struct.unpack_from("<H", data, start)[0]

        # Проверяем, что это аудио формат
        if format_tag in (1, 85, 255, 353, 0x0055, 0x0161, 0xFFFE):
            # nSamplesPerSec - точная частота дискретизации
            # (перезаписываем strh)
            sample_rate = struct.unpack_from("<I", data, start + 4)[0]
            if sample_rate > 0:
                result["sample_rate"] = sample_rate

    @classmethod
    def _webm_mkv_parse_info(cls, data: bytes) -> dict | None:  # noqa: C901
        """Парсит размеры и длительность из MKV/WebM файла."""
        if len(data) < 4:
            return None

        width = cls._webm_read_ebml_uint(data, b"\xb0")  # PixelWidth
        height = cls._webm_read_ebml_uint(data, b"\xba")  # PixelHeight
        duration = cls._webm_read_duration_seconds(data)

        # Видео: fps — пробуем FrameRate, затем DefaultDuration
        fps = cls._webm_read_ebml_float(data, b"\x23\x83\xe3")

        # Если FrameRate нет, считаем из DefaultDuration (наносекунды на фрейм)
        if fps is None:
            default_duration = cls._webm_read_ebml_uint(
                data, b"\x23\xe3\x83"
            )  # DefaultDuration
            if default_duration and default_duration > 0:
                fps = 1_000_000_000 / default_duration  # Конвертируем в fps

        # Аудио: sample_rate
        sample_rate = cls._webm_read_ebml_float(data, b"\xb5")

        # Номинальный битрейт (опционально)
        bitrate_nominal_raw = cls._webm_read_ebml_uint(data, b"\x25\x86\x88")
        bitrate_nominal: int | None = None
        if bitrate_nominal_raw is not None and bitrate_nominal_raw > 0:
            bitrate_nominal = bitrate_nominal_raw // 1000

        doc_type = cls._webm_read_ebml_string(data, b"\x42\x82")

        if doc_type == "webm":
            format = "WEBM"
        elif doc_type == "matroska":
            format = "MKV"
        else:
            format = cls._webm_ebml_detect_format_by_codecs(data)

        result: dict[str, Any] = {"format": format}

        if width and height:
            result["width"] = width
            result["height"] = height
        if duration is not None:
            result["duration"] = duration
        if fps is not None and fps > 0:
            result["fps"] = round(fps, 3)
        if sample_rate is not None and sample_rate > 0:
            result["sample_rate"] = round(sample_rate)
        result["bitrate_nominal"] = bitrate_nominal

        return result if len(result) > 1 else None

    @staticmethod
    def _webm_read_ebml_size_vint(
        data: bytes, start_pos: int
    ) -> tuple[int, int] | None:
        """Читает EBML VINT для size и возвращает (длина_vint, значение)."""
        if start_pos >= len(data):
            return None

        first = data[start_pos]
        mask = 0x80
        vint_len = 1
        while vint_len <= 8 and (first & mask) == 0:
            mask >>= 1
            vint_len += 1

        if vint_len > 8 or start_pos + vint_len > len(data):
            return None

        value = first & (mask - 1)
        for i in range(1, vint_len):
            value = (value << 8) | data[start_pos + i]

        return vint_len, value

    @classmethod
    def _webm_read_ebml_element_value(
        cls, data: bytes, element_id: bytes, parser: Callable
    ) -> Any:
        """
        Универсальный поиск и чтение EBML элемента.

        Args:
            data: сырые байты.
            element_id: ID элемента (bytes).
            parser: функция (raw_bytes) -> parsed_value или None.

        Returns:
            Распарсенное значение или None если элемент не найден.
        """
        pos = 0
        while True:
            idx = data.find(element_id, pos)
            if idx < 0:
                return None

            size_meta = cls._webm_read_ebml_size_vint(
                data, idx + len(element_id)
            )
            if not size_meta:
                pos = idx + 1
                continue

            size_len, value_len = size_meta
            value_start = idx + len(element_id) + size_len
            value_end = value_start + value_len
            if value_len <= 0 or value_end > len(data):
                pos = idx + 1
                continue

            result = parser(data[value_start:value_end])

            if result is not None:
                return result
            pos = idx + 1

    @classmethod
    def _webm_read_ebml_uint(
        cls, data: bytes, element_id: bytes
    ) -> int | None:
        """Ищет uint-элемент по ID и возвращает его value."""

        def _parse(raw: bytes) -> int | None:
            return int.from_bytes(raw, "big")

        return cls._webm_read_ebml_element_value(data, element_id, _parse)

    @classmethod
    def _webm_read_ebml_float(
        cls, data: bytes, element_id: bytes
    ) -> float | None:
        """Ищет float-элемент по ID и читает 4/8-байтовое значение."""

        def _parse(raw: bytes) -> float | None:
            if len(raw) == 4:
                return struct.unpack(">f", raw)[0]
            if len(raw) == 8:
                return struct.unpack(">d", raw)[0]
            return None

        return cls._webm_read_ebml_element_value(data, element_id, _parse)

    @classmethod
    def _webm_read_ebml_string(
        cls, data: bytes, element_id: bytes
    ) -> str | None:
        """Читает строковый элемент."""

        def _parse(raw: bytes) -> str | None:
            try:
                return raw.decode("ascii")
            except UnicodeDecodeError:
                return None

        return cls._webm_read_ebml_element_value(data, element_id, _parse)

    @staticmethod
    def _webm_ebml_detect_format_by_codecs(data: bytes) -> str | None:
        """
        Если DocType не найден, определяем формат по кодекам.

        WebM поддерживает только:
        - Видео: V_VP8, V_VP9, V_AV1
        - Аудио: A_VORBIS, A_OPUS

        Всё остальное — MKV.
        """
        if len(data) < 8 or data[:4] != b"\x1a\x45\xdf\xa3":
            return None

        # Всё, что не WebM → MKV
        webm_codecs = (b"V_VP8", b"V_VP9", b"V_AV1", b"A_VORBIS", b"A_OPUS")

        # Ищем любое упоминание кодеков
        for i in range(len(data) - 6):
            chunk = data[i : i + 6]
            if (
                chunk.startswith((b"V_", b"A_", b"S_"))
                and chunk not in webm_codecs
            ):
                return "MKV"

        return "WEBM"

    @classmethod
    def _webm_read_duration_seconds(cls, data: bytes) -> int | None:
        """Считывает WebM duration (сек) из Duration + TimecodeScale."""
        duration_raw = cls._webm_read_ebml_float(data, b"\x44\x89")  # Duration
        if duration_raw is None:
            return None

        timecode_scale = cls._webm_read_ebml_uint(
            data, b"\x2a\xd7\xb1"
        )  # TimecodeScale
        if not timecode_scale:
            timecode_scale = 1_000_000  # default 1ms

        # Duration в единицах TimecodeScale, конвертируем в секунды
        return round(duration_raw * (timecode_scale / 1_000_000_000))

    # =========================================================================
    # [ ] Парсеры: аудио
    # =========================================================================

    @classmethod
    def _mp3_parse_info(  # noqa: C901
        cls,
        head: bytes,
        tail: bytes | None = None,
        file_size: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Извлекает метаданные из MP3 по заголовку (начало или конец файла).

        Args:
            head: начальные байты файла (рекомендуется ≥32 КБ).
            tail: последние байты файла (для поиска Xing/VBRI/ID3v1).
            file_size: полный размер файла.

        Returns:
            dict с 'format', 'duration', 'sample_rate', 'bitrate' или None.
        """
        if len(head) < 4:
            return None

        result: dict[str, Any] = {"format": "MP3"}
        sample_rate: int | None = None
        bitrate: int | None = None
        duration: int | None = None

        if file_size and len(head) >= file_size:
            # Весь файл в head
            tail = head[-8192:]  # Берём конец head как tail

        # === Поиск фрейма: сначала в head, затем в tail ===
        frame_data = None
        frame_pos = None
        tag_size = None

        for data in (head, tail):
            if not data:
                continue

            start = 0
            # Пропускаем ID3v2 только в head
            if data is head and len(data) >= 10 and data[:3] == b"ID3":
                tag_size = (
                    ((data[6] & 0x7F) << 21)
                    | ((data[7] & 0x7F) << 14)
                    | ((data[8] & 0x7F) << 7)
                    | (data[9] & 0x7F)
                )
                start = 10 + tag_size

            pos = cls._mp3_find_frame_header(data, start)
            if pos is not None:
                frame_data = data
                frame_pos = pos
                break

        if frame_pos is None:
            return result

        # Парсим заголовок фрейма (big-endian)
        frame_data = cast(bytes, frame_data)
        header = struct.unpack(">I", frame_data[frame_pos : frame_pos + 4])[0]

        version_id = (header >> 19) & 0b11
        layer = (header >> 17) & 0b11
        bitrate_idx = (header >> 12) & 0b1111
        sample_rate_idx = (header >> 10) & 0b11

        # Извлекаем bitrate
        br_table = cls._mp3_bitrate_table(version_id, layer)
        if 0 <= bitrate_idx < len(br_table) and br_table[bitrate_idx]:
            bitrate = br_table[bitrate_idx]

        # Извлекаем sample_rate
        mp3_sample_rate_table = {
            0b11: [44100, 48000, 32000, None],  # MPEG-1
            0b10: [22050, 24000, 16000, None],  # MPEG-2
            0b00: [11025, 12000, 8000, None],  # MPEG-2.5
        }
        sr_table = mp3_sample_rate_table.get(version_id) or [None] * 4
        if 0 <= sample_rate_idx < len(sr_table) and sr_table[sample_rate_idx]:
            sample_rate = sr_table[sample_rate_idx]

        # Xing/VBRI — сначала там где нашли фрейм, затем в других данных
        xing_info = cls._mp3_parse_xing_vbri(frame_data, frame_pos)
        if not xing_info:
            other = tail if frame_data is head else head
            if other:
                other_pos = cls._mp3_find_frame_header(other, 0)
                if other_pos is not None:
                    xing_info = cls._mp3_parse_xing_vbri(other, other_pos)

        if xing_info and "duration_ms" in xing_info:
            duration = round(xing_info["duration_ms"] / 1000)
        elif xing_info and "frames" in xing_info and sample_rate:
            samples_per_frame = (
                1152 if layer == 0b01 else (576 if layer == 0b10 else 384)
            )
            total_samples = xing_info["frames"] * samples_per_frame
            duration = round(total_samples / sample_rate)
        elif file_size and bitrate:
            # Fallback для CBR: оценка по размеру
            audio_size = file_size
            # Вычитаем ID3v2 (в head)
            if tag_size:
                audio_size -= 10 + tag_size
            # Вычитаем ID3v1 (в tail)
            if tail and len(tail) >= 128 and tail[-128:-124] == b"TAG":
                audio_size -= 128
            if audio_size > 0:
                duration = round((audio_size * 8) / (bitrate * 1000))
                if not (1 <= duration <= 24 * 3600):
                    duration = None

        if bitrate:
            result["bitrate"] = bitrate
        if sample_rate:
            result["sample_rate"] = sample_rate
        if duration:
            result["duration"] = duration

        return result if len(result) > 1 else None

    @staticmethod
    def _mp3_find_frame_header(data: bytes, start: int) -> int | None:
        """Поиск заголовка первого аудио-фрейма после пропуска тегов."""
        for i in range(max(0, start), min(len(data) - 4, start + 65536)):
            if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
                # Проверка валидности версии и слоя
                version = (data[i + 1] >> 3) & 0x03
                layer = (data[i + 1] >> 1) & 0x03
                bitrate_idx = (data[i + 2] >> 4) & 0x0F
                sample_rate_idx = (data[i + 2] >> 2) & 0x03
                # Отбрасываем зарезервированные значения
                if (
                    version != 0b01
                    and layer != 0b00
                    and bitrate_idx != 0b1111
                    and sample_rate_idx != 0b11
                ):
                    return i
        return None

    @staticmethod
    def _mp3_bitrate_table(version_id: int, layer: int) -> list[int | None]:
        """Таблицы битрейтов по спецификации MPEG."""
        # fmt: off
        if version_id == 0b11 and layer == 0b01:  # MPEG-1 Layer III
            return [
                None,
                32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320,
                None,
            ]
        elif version_id != 0b11 and layer == 0b01:  # MPEG-2/2.5 Layer III
            return [
                None,
                8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160,
                None,
            ]
        elif version_id == 0b11 and layer == 0b10:  # MPEG-1 Layer II
            return [
                None,
                32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384,
                None,
            ]
        elif version_id != 0b11 and layer == 0b10:  # MPEG-2/2.5 Layer II
            return [
                None,
                8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160,
                None,
            ]
        elif version_id == 0b11 and layer == 0b11:  # MPEG-1 Layer I
            return [
                None,
                32, 64, 96, 128, 160, 192, 224, 256,288, 320, 352, 384,416,448,
                None,
            ]
        elif version_id != 0b11 and layer == 0b11:  # MPEG-2/2.5 Layer I
            return [
                None,
                32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256,
                None,
            ]
        return [None] * 16
        # fmt: on

    @staticmethod
    def _mp3_parse_xing_vbri(data: bytes, frame_pos: int) -> dict | None:
        """Парсинг Xing/VBRI заголовка для точной длительности VBR."""
        if frame_pos + 100 > len(data):
            return None

        version = (data[frame_pos + 1] >> 3) & 0b11
        offset = 21 if version == 0b11 else 36

        pos = frame_pos + offset
        if pos + 8 <= len(data) and data[pos : pos + 4] in (b"Xing", b"Info"):
            flags = struct.unpack(">I", data[pos + 4 : pos + 8])[0]
            result = {}
            if flags & 0x01 and pos + 12 <= len(data):  # Frames flag
                result["frames"] = struct.unpack(
                    ">I", data[pos + 8 : pos + 12]
                )[0]
            if flags & 0x02 and pos + 16 <= len(data):  # Bytes flag
                result["bytes"] = struct.unpack(
                    ">I", data[pos + 12 : pos + 16]
                )[0]
            if flags & 0x08 and pos + 20 <= len(data):  # Duration flag
                result["duration_ms"] = struct.unpack(
                    ">I", data[pos + 16 : pos + 20]
                )[0]
            return result or None

        # VBRI на смещении +32
        pos = frame_pos + 32
        if pos + 14 <= len(data) and data[pos : pos + 4] == b"VBRI":
            frames = struct.unpack(">I", data[pos + 10 : pos + 14])[0]
            if frames > 0:
                return {"frames": frames}

        return None

    @classmethod
    def _m4a_parse_audio_info(cls, data: bytes) -> dict | None:
        result = cls._mp4_parse_info(data) or {}
        out = {"format": "M4A"}
        if result.get("duration") is not None:
            out["duration"] = result["duration"]
        return out

    @staticmethod
    def _m4a_parse_mvhd_duration(data: bytes) -> int | None:
        """Парсит длительность из mvhd атома."""
        if len(data) < 20:
            return None

        version = data[8]  # Смещение 8 байт от начала атома

        if version == 0:
            # timescale (4 bytes) at offset 20
            if len(data) < 24:
                return None
            timescale = struct.unpack(">I", data[20:24])[0]
            # duration (4 bytes) at offset 24
            if len(data) < 28:
                return None
            duration = struct.unpack(">I", data[24:28])[0]
        else:  # version 1
            # timescale (4 bytes) at offset 20
            if len(data) < 24:
                return None
            timescale = struct.unpack(">I", data[20:24])[0]
            # duration (8 bytes) at offset 24
            if len(data) < 32:
                return None
            duration = struct.unpack(">Q", data[24:32])[0]

        if timescale > 0:
            return duration / timescale

        return None

    @classmethod
    def _ogg_parse_info(  # noqa: C901
        cls,
        head: bytes,
        tail: bytes | None,
        file_size: int | None = None,
    ) -> dict | None:
        """
        Извлекает метаданные из OGG/OGV файла.

        Args:
            head: Первые байты файла (заголовок).
            tail: Последние байты файла (хвост для поиска гранулы).
            content_type: MIME-тип файла (audio/ogg или video/ogg).

        Returns:
            dict с ключами format, duration, sample_rate, width, height, fps
            или None если формат не распознан.
            Без tail возвращает format + размеры/fps/sample_rate без duration.
        """
        # 1. Базовая валидация сигнатуры Ogg
        if len(head) < 27 or head[:4] != b"OggS":
            return None

        # 2. Парсим заголовки всех потоков (Vorbis/Theora) из BOS-страниц
        streams = cls._ogg_parse_all_streams(head)
        if not streams:
            return None

        has_video = any(
            s["type"] in ("theora", "vp8", "vp9", "av1") for s in streams
        )
        has_audio = any(
            s["type"] in ("vorbis", "opus", "flac", "speex") for s in streams
        )
        is_audio = has_audio and not has_video
        result: dict = {"format": "OGG" if is_audio else "OGV"}

        # Собираем всё что можно без tail
        for stream in streams:
            if stream["type"] == "vorbis":
                if sample_rate := stream.get("sample_rate"):
                    result["sample_rate"] = sample_rate
            elif stream["type"] == "theora":
                if w := stream.get("width"):
                    result["width"] = w
                if h := stream.get("height"):
                    result["height"] = h
                fps_num = stream.get("fps_num")
                fps_den = stream.get("fps_den")
                if fps_num and fps_den and fps_den > 0:
                    result["fps"] = round(fps_num / fps_den, 3)

        # Если нет tail — возвращаем что есть
        if not tail or len(tail) < 27:
            if file_size and len(head) >= file_size:
                # Весь файл в head — ищем последнюю гранулу в head
                tail = head[-8192:]  # Берём конец head как tail
            else:
                result["error_desc"] = (
                    "Для определения duration необходим "
                    "конец файла (tail) или файл целиком"
                )
                return result

        # 3. Проходим по каждому найденному потоку для извлечения метаданных
        # С tail — пытаемся получить длительность
        for stream in streams:
            serial = stream.get("serial")
            stream_type = stream["type"]

            # Извлекаем финальную гранулу именно для этого типа потока.
            granule = cls._ogg_extract_last_granule(tail, serial, stream_type)
            if not granule or granule <= 0:
                continue

            # --- Аудио-поток (Vorbis) ---
            if stream_type == "vorbis":
                sample_rate = stream.get("sample_rate")
                if sample_rate and sample_rate > 0:
                    if "sample_rate" not in result:
                        result["sample_rate"] = sample_rate
                    duration = granule / sample_rate
                    if 1 <= duration <= 86400:
                        result["duration"] = duration

            # --- Видео-поток (Theora) ---
            elif stream_type == "theora":
                # Считаем длительность из видео,
                # только если она ещё не задана аудио
                if "duration" not in result:
                    duration = cls._ogg_calculate_duration(stream, granule)
                    if duration and 1 <= duration <= 86400:
                        result["duration"] = duration

                # Добавляем видео-характеристики
                if w := stream.get("width"):
                    result["width"] = w
                if h := stream.get("height"):
                    result["height"] = h

                fps_num = stream.get("fps_num")
                fps_den = stream.get("fps_den")
                if fps_num and fps_den and fps_den > 0:
                    result["fps"] = round(fps_num / fps_den, 3)

        # 4. Фоллбэк: если длительность не найдена,
        # пытаемся получить её из любого Vorbis-потока
        # (Полезно, если serial в хвосте смещён
        # или страница с точным serial обрезана)
        if "duration" not in result:
            for stream in streams:
                if stream["type"] == "vorbis" and stream.get("sample_rate"):
                    granule = cls._ogg_extract_last_granule(
                        tail, None, "vorbis"
                    )
                    if granule and granule > 0:
                        dur = granule / stream["sample_rate"]
                        if 1 <= dur <= 86400:
                            result["duration"] = dur
                            if "sample_rate" not in result:
                                result["sample_rate"] = stream.get(
                                    "sample_rate"
                                )
                            break

        return result if len(result) > 1 else None

    @staticmethod
    def _ogg_parse_all_streams(data: bytes) -> list:  # noqa: C901
        """
        Извлекает метаданные всех потоков из BOS-страниц Ogg.

        Аргументы:
            data: Байты файла (начало или конец).

        Возвращает:
            Список словарей с метаданными потоков (Theora/Vorbis),
            отсортированный по приоритету (видео > аудио).
        """
        pos = 0
        streams: dict[int, dict] = {}

        while pos + 27 <= len(data):
            # Ищем сигнатуру страницы Ogg
            if data[pos : pos + 4] != b"OggS":
                pos += 1
                continue

            header_type = data[pos + 5]
            serial = struct.unpack("<I", data[pos + 14 : pos + 18])[0]
            page_seq = struct.unpack("<I", data[pos + 18 : pos + 22])[0]
            segments_count = data[pos + 26]

            # Проверяем границы сегментной таблицы
            seg_table_start = pos + 27
            seg_table_end = seg_table_start + segments_count
            if seg_table_end > len(data):
                break

            # Считаем полный размер страницы
            page_size = 27 + segments_count
            for i in range(segments_count):
                page_size += data[seg_table_start + i]
            if page_size > len(data):
                pos += 27 + segments_count
                continue

            # Обрабатываем только BOS-страницы с идентификационными пакетами
            if (header_type & 0x02) and page_seq == 0:
                payload_start = seg_table_end
                if payload_start + 7 <= len(data):
                    pkt_type = data[payload_start]

                    # Theora: 0x80 + "theora"
                    if (
                        pkt_type == 0x80
                        and payload_start + 34 <= len(data)
                        and data[payload_start + 1 : payload_start + 7]
                        == b"theora"
                    ):
                        # Извлекаем размеры (макроблоки → пиксели)
                        frame_w = struct.unpack(
                            ">H", data[payload_start + 10 : payload_start + 12]
                        )[0]
                        frame_h = struct.unpack(
                            ">H", data[payload_start + 12 : payload_start + 14]
                        )[0]
                        width = frame_w << 4
                        height = frame_h << 4

                        # Извлекаем FPS
                        fps_num = struct.unpack(
                            ">I", data[payload_start + 22 : payload_start + 26]
                        )[0]
                        fps_den = struct.unpack(
                            ">I", data[payload_start + 26 : payload_start + 30]
                        )[0]

                        # Используем дефолтный shift=6 (наиболее частый случай)
                        granule_shift = 6

                        # Валидация параметров
                        if (
                            0 < fps_den <= 10000
                            and 0 < fps_num <= 600000
                            and 16 <= width <= 8192
                            and 16 <= height <= 8192
                        ):
                            streams[serial] = {
                                "type": "theora",
                                "serial": serial,
                                "priority": 0,  # видео имеет высший приоритет
                                "width": width,
                                "height": height,
                                "fps_num": fps_num,
                                "fps_den": fps_den,
                                "granule_shift": granule_shift,
                            }

                    # Vorbis: 0x01 + "vorbis"
                    elif (
                        pkt_type == 0x01
                        and payload_start + 16 <= len(data)
                        and data[payload_start + 1 : payload_start + 7]
                        == b"vorbis"
                    ):
                        sample_rate = struct.unpack(
                            "<I", data[payload_start + 12 : payload_start + 16]
                        )[0]
                        if 8000 <= sample_rate <= 192000:
                            streams[serial] = {
                                "type": "vorbis",
                                "serial": serial,
                                "priority": 1,  # аудио имеет низший приоритет
                                "sample_rate": sample_rate,
                            }

            pos += page_size
            if pos <= 0 or pos >= len(data):
                break

        return sorted(streams.values(), key=lambda x: x["priority"])

    @staticmethod
    def _ogg_extract_last_granule(
        tail: bytes,
        expected_serial: int | None = None,
        stream_type: Literal["vorbis", "theora"] | None = None,
    ) -> int | None:
        """
        Находит последнюю валидную гранулу для указанного serial в хвосте файла

        Аргументы:
            tail: Байты хвоста файла.
            expected_serial: Ожидаемый serial потока (None = любой).
            stream_type: Тип потока для гибкой валидации гранулы.

        Возвращает:
            Значение гранулы или None, если не найдено.
        """
        pos = tail.rfind(b"OggS")
        while pos >= 0:
            if pos + 27 <= len(tail):
                version = tail[pos + 4]
                header_type = tail[pos + 5]
                granule = struct.unpack("<q", tail[pos + 6 : pos + 14])[0]
                serial = struct.unpack("<I", tail[pos + 14 : pos + 18])[0]
                segments_count = tail[pos + 26]

                # Быстрая проверка валидности заголовка
                if version != 0 or (header_type & 0xF0) != 0:
                    # ❌ Invalid version/header_type
                    pos = tail.rfind(b"OggS", 0, pos)
                    continue

                # Считаем конец страницы
                page_end = pos + 27 + segments_count
                for i in range(segments_count):
                    if pos + 27 + i < len(tail):
                        page_end += tail[pos + 27 + i]

                # Гибкая проверка гранулы в зависимости от типа потока
                granule_ok = granule > 0
                if stream_type == "vorbis":
                    # Аудио: гранула = сэмплы, макс ~24ч при 192kHz = 16.6 млрд
                    granule_ok = granule_ok and granule < 16_600_000_000
                else:
                    # Видео: гранула = кадры, макс ~24ч при 120fps = 10 млн
                    granule_ok = granule_ok and granule < 10_000_000

                if (
                    page_end <= len(tail)
                    and (expected_serial is None or serial == expected_serial)
                    and granule_ok
                ):
                    return granule
            pos = tail.rfind(b"OggS", 0, pos)

        return None

    @staticmethod
    def _ogg_calculate_duration(stream: dict, granule: int) -> float | None:
        """
        Считает длительность в секундах на основе гранулы и параметров потока.

        Аргументы:
            stream: Словарь с метаданными потока.
            granule: Значение гранулы из последней страницы.

        Возвращает:
            Длительность в секундах или None при ошибке.
        """
        if stream["type"] == "theora":
            fps_num = stream.get("fps_num")
            fps_den = stream.get("fps_den")
            if not fps_num or not fps_den or fps_den <= 0:
                return None
            shift = stream.get("granule_shift", 6)
            # Декодируем Theora granule: (keyframes << shift) | offset
            frames = (granule >> shift) + (granule & ((1 << shift) - 1))
            fps = fps_num / fps_den
            if fps <= 0 or fps > 120:
                return None
            return frames / fps

        elif stream["type"] == "vorbis":
            sr = stream.get("sample_rate")
            if not sr or sr <= 0:
                return None
            # Для Vorbis гранула = количество сэмплов
            return granule / sr

        return None

    @staticmethod
    def _aac_parse_info(  # noqa: C901
        data: bytes, file_size: int | None = None
    ) -> dict | None:
        """
        Оценивает длительность AAC-файла (ADTS) по начальному участку (~2 КБ).

        Args:
            data: Первые байты файла (рекомендуется ≥2048).
            file_size: Полный размер файла в байтах
                (опционально, для экстраполяции)

        Returns:
            dict с ключами:
                - 'format': 'AAC',
                - 'duration': длительность в секундах (int, опционально)
                - 'sample_rate': частота дискретизации в Гц (int, опционально)
                - 'bitrate': битрейт в kbps
                    (int, опционально, None если не найден)
            или None, если формат не распознан.
        """
        pos = 0
        total_samples = 0
        frame_count = 0
        sample_rate = None
        bitrate = None
        first_frame_pos = None
        # fmt: off
        aac_sample_rate_table = [
            96000, 88200, 64000, 48000, 44100, 32000,
            24000, 22050, 16000, 12000, 11025, 8000, 7350,
        ]
        # Таблица битрейтов для ADTS (MPEG-4 AAC), индекс 0-14, 15=свободный
        aac_bitrate_table = [
            None,
            8000, 16000, 24000, 32000, 48000, 64000, 80000, 96000,
            112000, 128000, 160000, 192000, 224000, 256000, 320000,
        ]
        # fmt: on
        # Пропускаем ID3v2-тег, если есть
        if data[:3] == b"ID3" and len(data) >= 10:
            id3_size = (
                ((data[6] & 0x7F) << 21)
                | ((data[7] & 0x7F) << 14)
                | ((data[8] & 0x7F) << 7)
                | (data[9] & 0x7F)
            )
            pos = min(id3_size + 10, len(data))

        while pos + 7 <= len(data):
            # Нули в середине восстановленного файла — данных больше нет
            if data[pos : pos + 8] == b"\x00" * 8:
                break

            # Поиск синхрослова ADTS: 0xFFF (12 бит)
            if data[pos] == 0xFF and (data[pos + 1] & 0xF0) == 0xF0:
                b1, b2, b3, b4, b5 = (
                    data[pos + 1],
                    data[pos + 2],
                    data[pos + 3],
                    data[pos + 4],
                    data[pos + 5],
                )

                protection_absent = b1 & 0x01
                header_size = 7 if protection_absent else 9

                # Разбор полей заголовка
                profile = (b2 >> 6) & 0x03
                sf_idx = (b2 >> 2) & 0x0F
                channel_config = ((b2 & 0x01) << 2) | ((b3 >> 6) & 0x03)
                bitrate_idx = (b3 >> 2) & 0x0F  # 4 бита битрейт-индекса

                # Валидация: отсев ложных синхрослов
                if sf_idx >= 13 or channel_config > 8 or profile > 3:
                    pos += 1
                    continue

                current_sr = (
                    aac_sample_rate_table[sf_idx]
                    if 0 <= sf_idx < len(aac_sample_rate_table)
                    else None
                )
                if not current_sr:
                    pos += 1
                    continue

                # Длина фрейма (13 бит, включает заголовок)
                frame_len = (
                    ((b3 & 0x03) << 11) | (b4 << 3) | ((b5 >> 5) & 0x07)
                )

                # Базовая валидация длины
                if frame_len < header_size or frame_len > 4096:
                    pos += 1
                    continue

                # Эвристика: отсев ложных срабатываний
                if (current_sr >= 32000 and frame_len < 90) or (
                    current_sr >= 16000 and frame_len < 60
                ):
                    pos += 1
                    continue

                # Фиксируем sample_rate и bitrate из первого валидного фрейма
                if sample_rate is None:
                    sample_rate = current_sr
                    first_frame_pos = pos
                if bitrate is None and 0 <= bitrate_idx < len(
                    aac_bitrate_table
                ):
                    br = aac_bitrate_table[bitrate_idx]
                    if br:
                        bitrate = br // 1000  # Конвертируем в kbps

                total_samples += 1024  # AAC-LC/Main/SSR: 1024 семпла на фрейм
                frame_count += 1

                if frame_count >= 50:
                    break

                pos += frame_len
                continue
            pos += 1

        result: dict[str, Any] = {"format": "AAC", "bitrate": bitrate}
        duration = 0
        if sample_rate and sample_rate > 0:
            result["sample_rate"] = sample_rate
            # Базовая длительность по найденным фреймам
            duration = total_samples / sample_rate
            result["duration"] = duration

        if total_samples == 0:
            return result

        # 📈 Экстраполяция по полному размеру файла
        if frame_count >= 3 and file_size and first_frame_pos is not None:
            parsed_bytes = pos - first_frame_pos
            if parsed_bytes > 0 and frame_count > 0:
                avg_frame_size = parsed_bytes / frame_count
                remaining_bytes = file_size - first_frame_pos
                estimated_frames = remaining_bytes / avg_frame_size
                estimated_samples = estimated_frames * 1024
                if sample_rate:
                    estimated_duration = estimated_samples / sample_rate
                    if estimated_duration > duration * 1.3:
                        result["duration"] = estimated_duration

        return result

    @staticmethod
    def _wav_parse_info(  # noqa: C901
        data: bytes, total_size: int | None = None
    ) -> dict | None:
        """
        Извлекает метаданные из WAV-файла по начальному участку заголовков.

        Args:
            data: Первые байты файла (заголовок RIFF/WAVE).
            total_size: Полный размер файла в байтах (опционально).

        Returns:
            dict с ключами:
                - 'format': 'WAV',
                - 'duration': длительность в секундах (int, опционально)
                - 'sample_rate': частота дискретизации в Гц (int, опционально)
                - 'bitrate': битрейт в kbps (int | None если не найден)
            или None, если файл не является валидным WAV.
        """
        if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
            return None

        byte_rate = None
        data_size = None
        data_start = None
        sample_rate = None
        bitrate = None  # По умолчанию None
        pos = 12
        limit = len(data)

        while pos + 8 <= limit:
            cid = data[pos : pos + 4]
            csize = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
            payload = pos + 8

            if cid == b"fmt " and csize >= 16 and payload + 12 <= limit:
                # fmt chunk: offset 4-7 = sample_rate, offset 8-11 = byte_rate
                sample_rate = struct.unpack(
                    "<I", data[payload + 4 : payload + 8]
                )[0]
                byte_rate = struct.unpack(
                    "<I", data[payload + 8 : payload + 12]
                )[0]
                # Рассчитываем битрейт: byte_rate * 8 / 1000 = kbps
                if byte_rate and byte_rate > 0:
                    bitrate = round((byte_rate * 8) / 1000)
            elif cid == b"data":
                data_size = csize
                data_start = payload

            # Переход к следующему чанку с выравниванием
            pos = payload + csize + (csize % 2)

        result: dict[str, Any] = {"format": "WAV", "bitrate": bitrate}
        if sample_rate and sample_rate > 0:
            result["sample_rate"] = sample_rate
        if not byte_rate or byte_rate == 0:
            return result

        # Определяем размер аудиоданных
        audio_bytes = None
        if data_size and data_size != 0xFFFFFFFF:
            audio_bytes = data_size
        elif total_size is not None and data_start is not None:
            audio_bytes = total_size - data_start
        elif total_size is not None:
            audio_bytes = total_size - 44

        if audio_bytes and audio_bytes > 0:
            result["duration"] = audio_bytes / byte_rate

        return result

    @staticmethod
    def _wma_parse_info(data: bytes) -> dict[str, Any] | None:  # noqa: C901
        """
        Извлекает метаданные из WMA/ASF-файла по заголовку.

        Аргументы:
            data: Первые байты файла (рекомендуется ≥8192 для надёжности).

        Возвращает:
            dict с ключами:
                - 'format': 'WMA'
                - 'duration': длительность в секундах (int, опционально)
                - 'sample_rate': частота дискретизации в Гц (int, опционально)
                - 'bitrate': битрейт в kbps (int | None если не найден)
            или None, если файл не является валидным ASF/WMA.
        """
        # === GUIDs в little-endian (стандарт ASF) ===
        asf_header_guid = (
            b"\x30\x26\xb2\x75\x8e\x66\xcf\x11\xa6\xd9\x00\xaa\x00\x62\xce\x6c"
        )
        file_props_guid = (
            b"\xa1\xdc\xab\x8c\x47\xa9\xcf\x11\x8e\xe4\x00\xc0\x0c\x20\x53\x65"
        )
        stream_props_guid = (
            b"\x91\x07\xdc\xb7\xb7\xa9\xcf\x11\x8e\xe6\x00\xc0\x0c\x20\x53\x65"
        )
        audio_stream_guid = (
            b"\x40\x9e\x69\xf8\x4d\x5b\xcf\x11\xa8\xfd\x00\x80\x5f\x5c\x44\x2b"
        )

        wma_format_tags = (0x0161, 0x0162, 0x0163)  # WMA v1, v2, Pro

        # Валидация заголовка ASF
        if len(data) < 30 or data[:16] != asf_header_guid:
            return None

        result: dict[str, Any] = {"format": "WMA"}
        sample_rate: int | None = None
        duration: int | None = None
        bitrate: int | None = None  # По умолчанию None

        # === 1️⃣ File Properties Object → длительность ===
        idx_fp = data.find(file_props_guid)
        if idx_fp >= 0 and idx_fp + 88 <= len(data):
            play_duration_100ns = struct.unpack(
                "<Q", data[idx_fp + 64 : idx_fp + 72]
            )[0]
            preroll_ms = struct.unpack("<Q", data[idx_fp + 80 : idx_fp + 88])[
                0
            ]
            dur = (play_duration_100ns / 10_000_000) - (preroll_ms / 1000)
            if dur > 0:
                duration = dur

        # === 2️⃣ Stream Properties Object → sample_rate и bitrate ===
        search_start = 0
        while True:
            idx_sp = data.find(stream_props_guid, search_start)
            if idx_sp == -1:
                break

            if idx_sp + 24 <= len(data):
                obj_size = struct.unpack(
                    "<Q", data[idx_sp + 16 : idx_sp + 24]
                )[0]
                if obj_size < 90 or idx_sp + obj_size > len(data):
                    search_start = idx_sp + 1
                    continue

                stream_type = data[idx_sp + 24 : idx_sp + 40]
                if stream_type == audio_stream_guid:
                    # Сканируем Type-Specific Data на предмет WAVEFORMATEX
                    for offset in range(60):  # Увеличили диапазон поиска
                        if idx_sp + 72 + offset + 8 > len(data):
                            break
                        fmt_tag = struct.unpack(
                            "<H",
                            data[
                                idx_sp + 72 + offset : idx_sp + 72 + offset + 2
                            ],
                        )[0]
                        if fmt_tag in wma_format_tags:
                            # sample_rate — DWORD на +4 от wFormatTag
                            if idx_sp + 72 + offset + 8 <= len(data):
                                sr = struct.unpack(
                                    "<I",
                                    data[
                                        idx_sp + 72 + offset + 4 : idx_sp
                                        + 72
                                        + offset
                                        + 8
                                    ],
                                )[0]
                                if 8000 <= sr <= 192000:
                                    sample_rate = sr
                            # bitrate — DWORD на +8 от wFormatTag
                            # (Average Bytes Per Sec * 8 / 1000)
                            if idx_sp + 72 + offset + 12 <= len(data):
                                avg_bytes_per_sec = struct.unpack(
                                    "<I",
                                    data[
                                        idx_sp + 72 + offset + 8 : idx_sp
                                        + 72
                                        + offset
                                        + 12
                                    ],
                                )[0]
                                if avg_bytes_per_sec > 0:
                                    bitrate = round(
                                        (avg_bytes_per_sec * 8) / 1000
                                    )
                            break
                    if sample_rate or bitrate:
                        break

            search_start = idx_sp + 1

        # === Сбор результата ===
        if duration:
            result["duration"] = duration
        if sample_rate:
            result["sample_rate"] = sample_rate
        result["bitrate"] = bitrate  # Всегда добавляем, даже если None

        return (
            result
            if (
                "duration" in result
                or "sample_rate" in result
                or bitrate is not None
            )
            else None
        )

    @staticmethod
    def _flac_parse_info(head: bytes) -> dict | None:
        """
        Парсит заголовок FLAC файла для получения sample rate,
        длительности и каналов.

        Примечание по битрейту:
        FLAC является форматом сжатия без потерь с переменным битрейтом (VBR).
        В заголовке FLAC отсутствует поле 'nominal bitrate' (номинальный
        битрейт), характерное для форматов с постоянным битрейтом (CBR) или
        некоторых других кодеков.
        Поэтому битрейт рассчитывается как среднее значение (average bitrate)
        по формуле: (Размер файла в битах) / (Длительность в секундах),
        если известен полный размер файла (file_size).

        Ищет первый METADATA_BLOCK_HEADER типа STREAMINFO (type 0).
        """
        if not head.startswith(b"fLaC"):
            return None

        pos = 4
        while pos + 4 <= len(head):
            # Читаем заголовок метаданных (4 байта)
            # Byte 0: Bit 7 = Last Block Flag, Bits 0-6 = Block Type
            header_byte = head[pos]
            is_last = (header_byte & 0x80) == 0x80
            block_type = header_byte & 0x7F

            # Bytes 1-3: Length of metadata block data
            block_size = int.from_bytes(
                head[pos + 1 : pos + 4], byteorder="big"
            )

            pos += 4

            if block_size > len(head) - pos:
                # Если данных недостаточно, прерываемся
                break

            if block_type == 0:  # STREAMINFO
                if block_size < 34:
                    return None

                streaminfo_data = head[pos : pos + 34]

                # Парсим 8 байт с середины STREAMINFO
                # (смещение 10 от начала блока данных)
                # Структура этих 8 байт:
                # 20 bits: Sample Rate
                # 3 bits: Channels - 1
                # 5 bits: Bits Per Sample - 1
                # 36 bits: Total Samples

                # Объединяем 8 байт в одно большое число для удобного сдвига
                # битов или парсим побайтово. Давайте побайтово для наглядности

                # Байты 10-12 содержат начало Sample Rate и часть Channels
                # Байты 12-13 содержат конец Channels
                # и Bits Per Sample и начало Total Samples

                # Проще всего взять 8 байт
                # начиная с offset 10 внутри блока STREAMINFO
                # Смещение в потоке данных: pos + 10
                raw_8_bytes = streaminfo_data[10:18]
                val = int.from_bytes(raw_8_bytes, byteorder="big")

                # Sample Rate: первые 20 бит
                sample_rate = val >> 44

                # Channels: следующие 3 бита
                channels_code = (val >> 41) & 0x07
                channels = channels_code + 1

                # Bits Per Sample: следующие 5 бит
                # bits_per_sample_code = (val >> 36) & 0x1F
                # bits_per_sample = bits_per_sample_code + 1

                # Total Samples: последние 36 бит
                total_samples = val & ((1 << 36) - 1)

                duration = None
                if sample_rate > 0 and total_samples > 0:
                    duration = total_samples / sample_rate

                return {
                    "sample_rate": sample_rate,
                    "channels": channels,
                    "duration": duration,
                    "format": "FLAC",
                }

            # Переходим к следующему блоку
            pos += block_size

            if is_last:
                break

        return None
