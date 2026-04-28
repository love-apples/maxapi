from __future__ import annotations

import asyncio
import base64
import mimetypes
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

import aiofiles
import aiofiles.os
import backoff
import puremagic
from aiohttp import (
    ClientConnectionError,
    ClientResponse,
    ClientSession,
    FormData,
)

from ..enums.api_path import ApiPath
from ..enums.update import UpdateType
from ..exceptions.download_file import DownloadFileError
from ..exceptions.max import InvalidToken, MaxApiError, MaxConnection
from ..loggers import logger_bot
from ..types.bot_mixin import BotMixin
from ..utils.runtime import bind_bot

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from backoff.types import Details
    from pydantic import BaseModel

    from ..bot import Bot
    from ..enums.http_method import HTTPMethod
    from ..enums.upload_type import UploadType


DOWNLOAD_CHUNK_SIZE = 65536


class _RetryableServerError(Exception):
    """Внутреннее исключение для retry при серверных ошибках."""

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(f"Server error {status}")


class NamedBytesIO(BytesIO):
    """
    BytesIO с поддержкой атрибута .name для единообразия с файловыми объектами.
    """

    __slots__ = ("name",)
    name: str | None

    def __init__(
        self, buffer: bytes = b"", *, name: str | None = None
    ) -> None:
        super().__init__(buffer)
        self.name = name  # Соответствует протоколу typing.BinaryIO


def _on_backoff(details: Details) -> None:
    """Логирование при retry.

    ``exception`` отсутствует в ``backoff.types.Details``, но реально
    присутствует в рантайме для ``on_exception``-хендлеров — это
    недоработка в типах самой библиотеки backoff.
    """
    wait = details["wait"]
    tries = details["tries"]
    exc = details["exception"]  # type: ignore[typeddict-item,assignment]
    if isinstance(exc, _RetryableServerError):
        logger_bot.warning(
            "Серверная ошибка %d, попытка %d, жду %.1fс",
            exc.status,
            tries,
            wait,
        )
    elif isinstance(exc, ClientConnectionError):
        logger_bot.warning(
            "Ошибка соединения (%s), попытка %d, жду %.1fс",
            exc,
            tries,
            wait,
        )


class BaseConnection(BotMixin):
    """
    Базовый класс для всех методов API.

    Содержит общую логику выполнения запроса (сериализация, отправка
    HTTP-запроса, обработка ответа).
    """

    API_URL = "https://platform-api.max.ru"
    RETRY_DELAY = 2
    ATTEMPTS_COUNT = 5
    AFTER_MEDIA_INPUT_DELAY = 2.0

    def __init__(self) -> None:
        """
        Инициализация BaseConnection.

        Атрибуты:
            bot: Экземпляр бота.
            session: aiohttp-сессия.
            after_input_media_delay: Задержка после ввода медиа.
        """

        self.bot: Bot | None = None
        self.session: ClientSession | None = None
        self.after_input_media_delay: float = self.AFTER_MEDIA_INPUT_DELAY
        self.api_url = self.API_URL

    def set_api_url(self, url: str) -> None:
        """
        Установка API URL для запросов

        Args:
            url: Новый API URL
        """

        self.api_url = url

    async def request(
        self,
        method: HTTPMethod,
        path: ApiPath | str,
        model: BaseModel | Any = None,
        *,
        is_return_raw: bool = False,
        **kwargs: Any,
    ) -> Any | BaseModel:
        """
        Выполняет HTTP-запрос к API с автоматическим retry
        при серверных ошибках.

        При получении HTTP-статуса из списка ``retry_on_statuses``
        (по умолчанию 502, 503, 504) запрос повторяется до
        ``max_retries`` раз с экспоненциальной задержкой.

        Args:
            method: HTTP-метод (GET, POST и т.д.).
            path: Путь до конечной точки.
            model: Pydantic-модель для
                десериализации ответа, если is_return_raw=False.
            is_return_raw: Если True — вернуть сырой
                ответ, иначе — результат десериализации.
            **kwargs: Дополнительные параметры (query, headers, json).

        Returns:
            model | dict | Error: Объект модели, dict или ошибка.

        Raises:
            RuntimeError: Если бот не инициализирован.
            MaxConnection: Ошибка соединения.
            InvalidToken: Ошибка авторизации (401).
            MaxApiError: Ошибка API (после исчерпания retry).
        """

        bot = self._ensure_bot()
        conn = bot.default_connection
        retry_statuses = conn.retry_on_statuses

        url = path.value if isinstance(path, ApiPath) else path

        @backoff.on_exception(
            backoff.expo,
            (ClientConnectionError, _RetryableServerError),
            max_tries=conn.max_retries + 1,
            factor=conn.retry_backoff_factor,
            on_backoff=_on_backoff,
        )
        async def _do_request() -> Any:
            session = await bot.ensure_session()
            resp = await session.request(
                method=method.value,
                url=url,
                **kwargs,
            )

            if resp.status == 401:
                await session.close()
                raise InvalidToken("Неверный токен!")

            if resp.status in retry_statuses:
                await resp.read()
                raise _RetryableServerError(resp.status)

            return resp

        try:
            response = await _do_request()
        except ClientConnectionError as e:
            raise MaxConnection(f"Ошибка при отправке запроса: {e}") from e
        except _RetryableServerError as e:
            raise MaxApiError(code=e.status, raw={"error": str(e)}) from e

        if not response.ok:
            raw = await response.json()
            if bot.dispatcher:
                asyncio.create_task(
                    bot.dispatcher.handle_raw_response(
                        UpdateType.RAW_API_RESPONSE, raw
                    )
                )
            raise MaxApiError(code=response.status, raw=raw)

        raw = await response.json()

        if bot.dispatcher:
            asyncio.create_task(
                bot.dispatcher.handle_raw_response(
                    UpdateType.RAW_API_RESPONSE, raw
                )
            )

        if is_return_raw:
            return raw

        model = model(**raw)  # type: ignore

        return bind_bot(model, bot)

    async def upload_file(self, url: str, path: str, type: UploadType) -> str:
        """
        Загружает файл на сервер.

        Args:
            url: URL загрузки.
            path: Путь к файлу.
            type: Тип файла.

        Returns:
            str: Сырой .text() ответ от сервера.
        """

        async with aiofiles.open(path, "rb") as f:
            file_data = await f.read()

        path_object = Path(path)
        basename = path_object.name

        form = FormData(quote_fields=False)
        form.add_field(
            name="data",
            value=file_data,
            filename=basename,
            content_type=mimetypes.guess_type(path)[0] or f"{type.value}/*",
        )

        bot = self._ensure_bot()

        session = bot.session
        if session is not None and not session.closed:
            async with session.post(url=url, data=form) as response:
                return await response.text()
        else:
            async with (
                ClientSession(
                    timeout=bot.default_connection.timeout
                ) as temp_session,
                temp_session.post(url=url, data=form) as response,
            ):
                return await response.text()

    async def upload_file_buffer(
        self, filename: str, url: str, buffer: bytes, type: UploadType
    ) -> str:
        """
        Загружает файл из буфера.

        Args:
            filename: Имя файла.
            url: URL загрузки.
            buffer: Буфер данных.
            type: Тип файла.

        Returns:
            str: Сырой .text() ответ от сервера.
        """

        try:
            matches = puremagic.magic_string(buffer[:4096])
            if matches:
                mime_type = matches[0][1]
                ext = mimetypes.guess_extension(mime_type) or ""
            else:
                mime_type = f"{type.value}/*"
                ext = ""
        except (OSError, ValueError):
            mime_type = f"{type.value}/*"
            ext = ""

        basename = f"{filename}{ext}"

        form = FormData(quote_fields=False)
        form.add_field(
            name="data",
            value=buffer,
            filename=basename,
            content_type=mime_type,
        )

        bot = self._ensure_bot()

        session = bot.session
        if session is not None and not session.closed:
            async with session.post(url=url, data=form) as response:
                return await response.text()
        else:
            async with (
                ClientSession(
                    timeout=bot.default_connection.timeout
                ) as temp_session,
                temp_session.post(url=url, data=form) as response,
            ):
                return await response.text()

    async def _fetch_response(self, url: str) -> ClientResponse:
        bot = self._ensure_bot()
        session = await bot.ensure_session()
        conn = bot.default_connection

        @backoff.on_exception(
            backoff.expo,
            (ClientConnectionError, _RetryableServerError),
            max_tries=conn.max_retries + 1,
            factor=conn.retry_backoff_factor,
            on_backoff=_on_backoff,
        )
        async def _do_request() -> Any:
            resp = await session.request("GET", url)
            if resp.status in conn.retry_on_statuses:
                await resp.read()
                raise _RetryableServerError(resp.status)
            return resp

        try:
            response = await _do_request()
        except ClientConnectionError as e:
            raise DownloadFileError(f"Network error: {e}") from e
        except _RetryableServerError as e:
            raise DownloadFileError(
                f"Ошибка при скачивании файла: HTTP {e.status}"
            ) from e

        if not response.ok:
            response.release()
            raise DownloadFileError(
                f"Ошибка при скачивании: HTTP {response.status}"
            )

        return response

    async def _fetch_content_stream(
        self,
        response: ClientResponse,
        *,
        chunk_size: int = DOWNLOAD_CHUNK_SIZE,
    ) -> AsyncIterator[bytes]:
        """
        Асинхронный генератор, который отдаёт чанки файла по мере скачивания.

        Args:
            response: Предварительно полученный ClientResponse.
                      Результат метода self._fetch_response

        Yields:
            bytes: Чанки данных файла.

        Raises:
            DownloadFileError: при ошибке запроса или недопустимом статусе.
        """
        if response.closed:
            raise DownloadFileError("response соединение закрыто")

        if not response.ok:
            response.release()
            raise DownloadFileError(
                f"Ошибка при скачивании: HTTP {response.status}"
            )

        try:
            async for chunk in response.content.iter_chunked(chunk_size):
                yield chunk
        finally:
            response.release()

    @staticmethod
    def _get_image_id(r: str) -> str | None:
        """
        Извлекает уникальную часть из токена изображения ссылки вида
        https://i.oneme.ru/i?r=image_token_base64url
        Args:
            r: Параметр из url

        Returns:
            str: Уникальная часть токена
            None: В случае ошибки ил ине верного формата
        """
        # Добавляем паддинг и конвертируем base64url
        r += "=" * (-len(r) % 4)
        # Конвертируем base64url в стандартный base64
        r = r.replace("-", "+").replace("_", "/")
        try:
            data = base64.b64decode(r)
        except Exception:
            return None

        if len(data) < 50:
            return None

        # Заголовок и хвост одинаковы для ссылок одного бота
        # head = base64.urlsafe_b64encode(data[0:16]).rstrip(b'=').decode()
        # tail = base64.urlsafe_b64encode(data[:-16]).rstrip(b'=').decode()

        # уникальный идентификатор изобраения для текущего бота
        image_id = base64.urlsafe_b64encode(data[18:-16]).rstrip(b"=").decode()
        return image_id

    def _capture_filename(self, response: ClientResponse) -> str:
        """
        Получает имя файла из заголовков
        Используется в _fetch_content_stream

        Args:
            response: Ответ сервера с заголовками файла

        Returns:
            str: Имя файла из заголовков.
            Если не удалось определить, то возвращается default
            в формате %y%m%d_%H%M%S.ext
        """
        filename = ext = ""
        datetime_str = datetime.now().strftime("%y%m%d_%H%M%S")
        if not isinstance(response, ClientResponse):
            raise TypeError(
                f"Ожидается ClientResponse, получен {type(response)}"
            )
        try:
            cd = response.content_disposition
            if cd and cd.filename:
                filename = Path(cd.filename).name
                ext = Path(filename).suffix
            else:
                name = response.url.name
                filename = Path(name).name  # Защита от path traversal
                ext = Path(filename).suffix
                if not ext:
                    if response.content_type:
                        ext = mimetypes.guess_extension(response.content_type)
                    if ext:
                        filename = f"{filename}{ext}"

            # Сервера Max возвращают имя файла дважды закодированное. Проверяем
            if re.search(r"%[0-9A-Fa-f]{2}", filename):
                filename = unquote(filename, encoding="utf-8")

            if response.url.host == "i.oneme.ru":
                # is_sticker
                if response.url.name == "getSmile":
                    if not ext or ext == ".bin":
                        ext = ".png"
                    if smileId := response.url.query.get("smileId"):
                        filename = f"sticker_{smileId}{ext}"
                    else:
                        filename = f"sticker_{datetime_str}{ext}"
                # is_image
                if response.url.name == "i":
                    if not ext or ext == ".bin":
                        ext = ".webp"
                    if (r_value := response.url.query.get("r")) and (
                        image_id := self._get_image_id(r_value)
                    ):
                        filename = f"image_{image_id}{ext}"
                    else:
                        filename = f"image_{datetime_str}{ext}"

            # Если имя не определилось
            if not filename or filename.startswith("."):
                if not ext:
                    ext = ".bin"
                filename = f"{datetime_str}{ext}"

        except (AttributeError, TypeError, ValueError) as e:
            logger_bot.warning(
                "Не удалось определить имя файла из заголовков: %s", e
            )
            if not filename:
                filename = f"{datetime_str}.bin"  # fallback

        return filename

    @staticmethod
    def _check_file_exists(path: Path | str) -> Path:
        """
        Проверяет, если файл существует, то возвращает
        новый свободный путь для сохранения Windows style:
        - file_name.ext
        - file_name(2).ext
        - file_name(3).ext

        Args:
            path (pathlib.Path): Путь к файлу

        Returns:
            pathlib.Path: Свободное имя файла с путём для сохранения

        Raises:
            ValueError: Non-encodable path.
        """
        path = Path(path)

        dest = path.parent

        if path.exists():
            max_num = 1  # Один уже существует
            fname, ext = path.stem, path.suffix
            pattern = re.compile(
                rf"^{re.escape(fname)}\((\d+)\){re.escape(ext)}$"
            )

            # Сканируем директорию
            for existing_path in dest.iterdir():
                match = pattern.match(existing_path.name)
                if match:
                    num = int(match.group(1))
                    if num > max_num:
                        max_num = num

            path = dest / f"{fname}({max_num + 1}){ext}"

        return path

    async def download_file(
        self,
        url: str,
        destination: Path | str,
        *,
        chunk_size: int = DOWNLOAD_CHUNK_SIZE,
    ) -> Path:
        """
        Скачивает файл по URL и сохраняет на диск.

        Метод работает не через общий ``request()``, поскольку
        ответом является бинарный поток, а не JSON.

        Если файл существует, то возвращает новый свободный путь для сохранения

        Windows style:
        - file_name.ext
        - file_name(2).ext
        - file_name(3).ext

        Args:
            url: URL файла для скачивания (из payload.url вложения).
            destination: Путь к директории для сохранения файла.
                Если путь не содержит имя файла (не имеет расширения),
                то будет использовано имя, предоставляемое сервером
                или значение по умолчанию.
                Если путь содержит расширение, он трактуется как
                полное имя файла для сохранения.
            chunk_size: Размер чанка при потоковом чтении
                (по умолчанию 64 КБ).

        Returns:
            Path: Полный путь к скачанному файлу.

        Raises:
            DownloadFileError: при ошибке скачивания.
        """
        dest = Path(destination)

        # Получаем ответ для определения имени файла из заголовков
        response = await self._fetch_response(url)

        # Определяем конечный путь для сохранения:
        # - если destination имеет расширение (суффикс) → это имя файла
        # - иначе → это директория, добавляем имя из ответа
        if dest.suffix:
            # destination содержит имя файла с расширением
            await aiofiles.os.makedirs(dest.parent, exist_ok=True)
            final_path = self._check_file_exists(dest)
        else:
            # destination - это директория, добавляем имя файла из ответа
            await aiofiles.os.makedirs(dest, exist_ok=True)
            filename = self._capture_filename(response)
            final_path = self._check_file_exists(dest / filename)

        try:
            async with aiofiles.open(final_path, "wb") as f:
                async for chunk in self._fetch_content_stream(
                    response, chunk_size=chunk_size
                ):
                    await f.write(chunk)
        except Exception:
            # При любой ошибке удаляем частично записанный файл
            if final_path.exists():
                final_path.unlink()
            raise

        return final_path

    async def download_bytes_io(
        self,
        url: str,
        *,
        chunk_size: int = DOWNLOAD_CHUNK_SIZE,
    ) -> NamedBytesIO:
        """
        Скачивает файл по URL и возвращает file-like объект в памяти.

        Внимание: весь файл загружается в оперативную память.
        Не используйте для файлов >100–200 МБ без контроля.

        Args:
            url: URL файла.
            chunk_size: Размер чанка при потоковом чтении.

        Returns:
            NamedBytesIO: Содержимое файла с атрибутом .name.
            Наследуется от io.BytesIO
            Для zero-copy передачи используйте .getbuffer(),
            для получения bytes — .read() или .getvalue().

        Raises:
            DownloadFileError: при ошибке скачивания.
        """
        bio = NamedBytesIO()

        response = await self._fetch_response(url)
        bio.name = self._capture_filename(response)

        async for chunk in self._fetch_content_stream(
            response,
            chunk_size=chunk_size,
        ):
            bio.write(chunk)

        bio.seek(0)  # обязательно переходим в начало

        return bio

    async def download_bytes(
        self,
        url: str,
        *,
        chunk_size: int = DOWNLOAD_CHUNK_SIZE,
    ) -> bytes:
        """
        Скачивает файл по URL и возвращает bytes в памяти.

        Внимание: весь файл загружается в оперативную память.
        Не используйте для файлов >100–200 МБ без контроля.

        Args:
            url: URL файла.
            chunk_size: Размер чанка при потоковом чтении.

        Returns:
            bytes: Содержимое файла

        Raises:
            DownloadFileError: при ошибке скачивания.
        """
        bio = await self.download_bytes_io(url=url, chunk_size=chunk_size)

        return bio.read()
