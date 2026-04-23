from __future__ import annotations

import asyncio
import inspect
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Awaitable, Callable, Optional
from urllib.parse import urlparse, unquote
from datetime import datetime
import re
import uuid

import aiofiles
import aiofiles.os
import backoff
import puremagic
from aiohttp import ClientConnectionError, ClientSession, FormData, ClientResponse

from ..enums.api_path import ApiPath
from ..enums.update import UpdateType
from ..exceptions.download_file import DownloadFileError
from ..exceptions.max import InvalidToken, MaxApiError, MaxConnection
from ..loggers import logger_bot
from ..types.bot_mixin import BotMixin
from ..utils.runtime import bind_bot

if TYPE_CHECKING:
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
            bot (Optional[Bot]): Экземпляр бота.
            session (Optional[ClientSession]): aiohttp-сессия.
            after_input_media_delay (float): Задержка после ввода медиа.
        """

        self.bot: Bot | None = None
        self.session: ClientSession | None = None
        self.after_input_media_delay: float = self.AFTER_MEDIA_INPUT_DELAY
        self.api_url = self.API_URL

    def set_api_url(self, url: str) -> None:
        """
        Установка API URL для запросов

        Args:
            url (str): Новый API URl
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
            method (HTTPMethod): HTTP-метод (GET, POST и т.д.).
            path (ApiPath | str): Путь до конечной точки.
            model (BaseModel | Any, optional): Pydantic-модель для
                десериализации ответа, если is_return_raw=False.
            is_return_raw (bool, optional): Если True — вернуть сырой
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
            url (str): URL загрузки.
            path (str): Путь к файлу.
            type (UploadType): Тип файла.

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
            response = await session.post(url=url, data=form)
            return await response.text()
        else:
            async with ClientSession(
                timeout=bot.default_connection.timeout
            ) as temp_session:
                response = await temp_session.post(url=url, data=form)
                return await response.text()

    async def upload_file_buffer(
        self, filename: str, url: str, buffer: bytes, type: UploadType
    ) -> str:
        """
        Загружает файл из буфера.

        Args:
            filename (str): Имя файла.
            url (str): URL загрузки.
            buffer (bytes): Буфер данных.
            type (UploadType): Тип файла.

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
            response = await session.post(url=url, data=form)
            return await response.text()
        else:
            async with ClientSession(
                timeout=bot.default_connection.timeout
            ) as temp_session:
                response = await temp_session.post(url=url, data=form)
                return await response.text()


    async def _fetch_content_stream(
        self,
        url: str,
        *,
        chunk_size: int = DOWNLOAD_CHUNK_SIZE,
        on_response: Optional[Callable[[ClientResponse], None | Awaitable[None]]] = None,
    ) -> AsyncIterator[bytes]:
        """
        Асинхронный генератор, который отдаёт чанки файла по мере скачивания.

        Args:
            url: URL файла.
            on_response: Опциональный коллбек, вызываемый с объектом ответа
                        до начала чтения тела. Позволяет извлечь заголовки.
                        Поддерживаются как синхронные функции, так и async def.
                        Если передана асинхронная функция, она будет автоматически awaited

        Yields:
            bytes: Чанки данных файла.

        Raises:
            DownloadFileError: при ошибке запроса или недопустимом статусе.
        """
        bot = self._ensure_bot()
        conn = bot.default_connection

        @backoff.on_exception(
            backoff.expo,
            (ClientConnectionError, _RetryableServerError),
            max_tries=conn.max_retries + 1,
            factor=conn.retry_backoff_factor,
            on_backoff=_on_backoff,
        )
        async def _do_download() -> Any:
            session = await bot.ensure_session()
            resp = await session.request("GET", url)
            if resp.status in conn.retry_on_statuses:
                await resp.read()
                raise _RetryableServerError(resp.status)
            return resp

        try:
            response = await _do_download()
        except ClientConnectionError as e:
            raise DownloadFileError(f"Ошибка при скачивании файла: {e}") from e
        except _RetryableServerError as e:
            raise DownloadFileError(
                f"Ошибка при скачивании файла: HTTP {e.status}"
            ) from e

        if not response.ok:
            raise DownloadFileError(
                f"Ошибка при скачивании файла: HTTP {response.status}"
            )

        if on_response is not None:
            result = on_response(response)
            if inspect.iscoroutine(result):
                await result

        try:
            async for chunk in response.content.iter_chunked(chunk_size):
                yield chunk
        finally:
            await response.release()


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
            chunk_size: Размер чанка при потоковом чтении
                (по умолчанию 64 КБ).

        Returns:
            Path: Полный путь к скачанному файлу.

        Raises:
            DownloadFileError: при ошибке скачивания.
        """
        dest = Path(destination)
        filename: Optional[str] = None # Переменная для хранения итогового имени
        ext: Optional[str] = None # расширение файла из заголовков

        await aiofiles.os.makedirs(destination, exist_ok=True)
        temp_filename = f"tmp_{uuid.uuid4().hex}.part"
        temp_path = dest / temp_filename

        def check_exists(path: Path) -> Path:
            """Проверяет, если файл существует, то возвращает новый свободный путь для сохранения"""

            if path.exists():
                max_num = 1 # Один уже существует
                fname, ext = path.stem, path.suffix
                pattern = re.compile(rf"^{re.escape(fname)}\((\d+)\){re.escape(ext)}$")

                # Сканируем директорию
                for existing_path in dest.iterdir():
                    if existing_path.suffix == '.part':
                        continue

                    match = pattern.match(existing_path.name)
                    if match:
                        num = int(match.group(1))
                        if num > max_num:
                            max_num = num

                path = dest / f"{fname}({max_num+1}){ext}"

            return path


        def capture_filename(response: Any) -> None:
            """Получает имя файла из заголовков"""
            nonlocal filename, ext
            try:
                cd = response.content_disposition
                if cd and cd.filename:
                    filename = Path(cd.filename).name
                    ext = Path(filename).suffix
                else:
                    parsed = urlparse(url)
                    name = unquote(parsed.path, encoding='utf-8', errors='replace')
                    filename = Path(name).name  # Защита от path traversal
                    ext = Path(filename).suffix
                    if not ext:
                        ext = mimetypes.guess_extension(response.content_type or "")
                        filename = f"{filename}{ext}"

                if re.search(r'%[0-9A-Fa-f]{2}', filename):
                    # Сервера Max возвращают имя файла дважды закодированное. Проверяем
                    filename = unquote(filename, encoding='utf-8', errors='replace')

            except (AttributeError, TypeError, ValueError) as e:
                logger_bot.warning("Не удалось определить имя файла из заголовков: %s. Используется дефолт", e)


        async with aiofiles.open(temp_path, "wb") as f:
            async for chunk in self._fetch_content_stream(
                url,
                chunk_size=chunk_size,
                on_response=capture_filename
            ):
                await f.write(chunk)

        # Если имя не определилось
        datetime_str = datetime.now().strftime("%y%m%d_%H%M%S")
        is_photo = url.startswith("https://i.oneme.ru/")
        if not filename or filename.startswith("."):
            if is_photo:
                if not ext:
                    ext = '.webp'
                filename = f"image_{datetime_str}{ext}"
            else:
                if not ext:
                    ext = '.bin'
                filename = f"{datetime_str}.bin"
        elif is_photo:
            filename = f"image_{datetime_str}{Path(filename).suffix}"

        final_path = check_exists(dest / filename)
        if final_path != temp_path:
            temp_path.replace(final_path)

        return final_path


    async def download_file_as_bytes(
        self,
        url: str,
        *,
        chunk_size: int = DOWNLOAD_CHUNK_SIZE,
    ) -> bytes:
        """
        Скачивает файл по URL и возвращает его содержимое как bytes.

        Внимание: весь файл загружается в оперативную память.
        Не используйте для файлов >100–200 МБ без контроля.

        Args:
            url: URL файла.
            chunk_size: Размер чанка при потоковом чтении.

        Returns:
            bytes: Содержимое файла.

        Raises:
            DownloadFileError: при ошибке скачивания.
        """
        chunks: list[bytes] = []
        async for chunk in self._fetch_content_stream(url, chunk_size=chunk_size):
            chunks.append(chunk)
        return b"".join(chunks)
