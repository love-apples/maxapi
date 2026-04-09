from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles
import puremagic
from aiohttp import ClientConnectionError, ClientSession, FormData

from ..enums.api_path import ApiPath
from ..enums.update import UpdateType
from ..exceptions.download_file import DownloadFileError
from ..exceptions.max import InvalidToken, MaxApiError, MaxConnection
from ..loggers import logger_bot
from ..types.bot_mixin import BotMixin

if TYPE_CHECKING:
    from pydantic import BaseModel

    from ..bot import Bot
    from ..enums.http_method import HTTPMethod
    from ..enums.upload_type import UploadType


DOWNLOAD_CHUNK_SIZE = 65536


async def _retry_request(
    session: ClientSession,
    method: str,
    url: str,
    *,
    max_retries: int,
    retry_statuses: tuple[int, ...],
    backoff_factor: float,
    **kwargs: Any,
) -> Any:
    """
    Выполняет HTTP-запрос с retry и экспоненциальным backoff.

    Повторяет запрос при ошибках соединения и серверных
    ошибках из retry_statuses.
    """
    for attempt in range(max_retries + 1):
        try:
            response = await session.request(method, url, **kwargs)
        except ClientConnectionError as e:
            if attempt < max_retries:
                delay = backoff_factor * (2**attempt)
                logger_bot.warning(
                    "Ошибка соединения (%s), попытка %d/%d, жду %.1fс",
                    e,
                    attempt + 1,
                    max_retries + 1,
                    delay,
                )
                await asyncio.sleep(delay)
                continue
            raise

        if response.status in retry_statuses and attempt < max_retries:
            await response.read()
            delay = backoff_factor * (2**attempt)
            logger_bot.warning(
                "Серверная ошибка %d, попытка %d/%d, жду %.1fс",
                response.status,
                attempt + 1,
                max_retries + 1,
                delay,
            )
            await asyncio.sleep(delay)
            continue

        return response

    return response  # последняя попытка


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

        if not bot.session:
            bot.session = ClientSession(
                base_url=bot.api_url,
                timeout=bot.default_connection.timeout,
                headers=bot.headers,
                **bot.default_connection.kwargs,
            )

        conn = bot.default_connection
        max_retries = conn.max_retries
        retry_statuses = conn.retry_on_statuses
        backoff_factor = conn.retry_backoff_factor

        url = path.value if isinstance(path, ApiPath) else path

        try:
            r = await _retry_request(
                bot.session,
                method.value,
                url,
                max_retries=max_retries,
                retry_statuses=retry_statuses,
                backoff_factor=backoff_factor,
                **kwargs,
            )
        except ClientConnectionError as e:
            raise MaxConnection(f"Ошибка при отправке запроса: {e}") from e

        if r.status == 401:
            await bot.session.close()
            raise InvalidToken("Неверный токен!")

        if not r.ok:
            raw = await r.json()
            if bot.dispatcher:
                asyncio.create_task(
                    bot.dispatcher.handle_raw_response(
                        UpdateType.RAW_API_RESPONSE, raw
                    )
                )
            raise MaxApiError(code=r.status, raw=raw)

        raw = await r.json()

        if bot.dispatcher:
            asyncio.create_task(
                bot.dispatcher.handle_raw_response(
                    UpdateType.RAW_API_RESPONSE, raw
                )
            )

        if is_return_raw:
            return raw

        model = model(**raw)  # type: ignore

        if hasattr(model, "message"):
            attr = model.message
            if hasattr(attr, "bot"):
                attr.bot = bot

        if hasattr(model, "bot"):
            model.bot = bot  # type: ignore

        return model

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
        ext = path_object.suffix

        form = FormData(quote_fields=False)
        form.add_field(
            name="data",
            value=file_data,
            filename=basename,
            content_type=f"{type.value}/{ext.lstrip('.')}",
        )

        bot = self._ensure_bot()

        session = bot.session
        if session is not None and not session.closed:
            response = await session.post(url=url, data=form)
            return await response.text()
        else:
            async with ClientSession() as temp_session:
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
        except Exception:
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
            async with ClientSession() as temp_session:
                response = await temp_session.post(url=url, data=form)
                return await response.text()

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

        Args:
            url: URL файла для скачивания (из payload.url вложения).
            destination: Путь к директории для сохранения файла.
            chunk_size: Размер чанка при потоковом чтении
                (по умолчанию 64 КБ).

        Returns:
            Path: Полный путь к скачанному файлу.

        Raises:
            DownloadFileError: При ошибке скачивания.
        """
        bot = self._ensure_bot()
        session = await bot.ensure_session()

        conn = bot.default_connection
        max_retries = conn.max_retries
        backoff_factor = conn.retry_backoff_factor
        retry_statuses = conn.retry_on_statuses

        try:
            response = await _retry_request(
                session,
                "GET",
                url,
                max_retries=max_retries,
                retry_statuses=retry_statuses,
                backoff_factor=backoff_factor,
            )
        except ClientConnectionError as e:
            raise DownloadFileError(f"Ошибка при скачивании файла: {e}") from e

        if not response.ok:
            raise DownloadFileError(
                f"Ошибка при скачивании файла: HTTP {response.status}"
            )

        cd = response.content_disposition
        if cd and cd.filename:
            filename = Path(cd.filename).name
        else:
            ext = mimetypes.guess_extension(response.content_type or "") or ""
            filename = f"file{ext}"

        path = Path(destination) / filename

        async with aiofiles.open(path, "wb") as f:
            async for chunk in response.content.iter_chunked(chunk_size):
                await f.write(chunk)

        return path
