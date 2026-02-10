from __future__ import annotations

import asyncio
import mimetypes
import os
from typing import TYPE_CHECKING, Any, Optional

import aiofiles
import puremagic
from aiohttp import ClientConnectionError, ClientSession, FormData
from pydantic import BaseModel

from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..enums.upload_type import UploadType
from ..exceptions.max import InvalidToken, MaxApiError, MaxConnection
from ..loggers import logger_connection
from ..types.bot_mixin import BotMixin

if TYPE_CHECKING:
    from ..bot import Bot


class BaseConnection(BotMixin):
    """Базовый класс для всех методов API.

    Содержит общую логику выполнения запроса
    (сериализация, отправка HTTP-запроса, обработка ответа).
    """

    API_URL = "https://platform-api.max.ru"
    RETRY_DELAY = 2
    ATTEMPTS_COUNT = 5
    AFTER_MEDIA_INPUT_DELAY = 2.0

    def __init__(self) -> None:
        """Инициализация BaseConnection.

        Атрибуты:
            bot (Optional[Bot]): Экземпляр бота.
            session (Optional[ClientSession]): aiohttp-сессия.
            after_input_media_delay (float): Задержка после ввода медиа.
        """

        self.bot: Optional[Bot] = None
        self.session: Optional[ClientSession] = None
        self.after_input_media_delay: float = self.AFTER_MEDIA_INPUT_DELAY
        self.api_url = self.API_URL

    def set_api_url(self, url: str) -> None:
        """Установка API URL для запросов.

        Args:
            url: Новый API URL.
        """

        self.api_url = url

    def _fire_raw_response(
        self, bot: "Bot", raw: Any
    ) -> None:
        """Запускает обработку сырого ответа API в фоне.

        Args:
            bot: Экземпляр бота.
            raw: Сырой JSON-ответ.
        """

        if not bot.dispatcher:
            return

        from ..enums.update import UpdateType

        task = asyncio.create_task(
            bot.dispatcher.handle_raw_response(
                UpdateType.RAW_API_RESPONSE, raw
            )
        )
        task.add_done_callback(self._handle_bg_task_result)

    @staticmethod
    def _handle_bg_task_result(task: asyncio.Task[Any]) -> None:
        """Callback для фоновых задач — логирует исключения.

        Args:
            task: Завершённая asyncio-задача.
        """

        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger_connection.error(
                "Ошибка в фоновой задаче RAW_API_RESPONSE: %s: %s",
                exc.__class__.__name__,
                exc,
            )

    async def request(
        self,
        method: HTTPMethod,
        path: ApiPath | str,
        model: BaseModel | Any = None,
        is_return_raw: bool = False,
        **kwargs: Any,
    ) -> Any | BaseModel:
        """Выполняет HTTP-запрос к API.

        Args:
            method: HTTP-метод (GET, POST и т.д.).
            path: Путь до конечной точки.
            model: Pydantic-модель для десериализации ответа,
                если is_return_raw=False.
            is_return_raw: Если True — вернуть сырой ответ,
                иначе — результат десериализации.
            **kwargs: Дополнительные параметры (query, headers, json).

        Returns:
            Объект модели, dict или ошибка.

        Raises:
            RuntimeError: Если бот не инициализирован.
            MaxConnection: Ошибка соединения.
            InvalidToken: Ошибка авторизации (401).
        """

        bot = self._ensure_bot()

        if not bot.session:
            bot.session = ClientSession(
                base_url=bot.api_url,
                timeout=bot.default_connection.timeout,
                headers=bot.headers,
                **bot.default_connection.kwargs,
            )

        try:
            r = await bot.session.request(
                method=method.value,
                url=path.value if isinstance(path, ApiPath) else path,
                **kwargs,
            )
        except ClientConnectionError as e:
            raise MaxConnection(f"Ошибка при отправке запроса: {e}")

        if r.status == 401:
            await bot.session.close()
            raise InvalidToken("Неверный токен!")

        if not r.ok:
            raw = await r.json()
            self._fire_raw_response(bot, raw)
            raise MaxApiError(code=r.status, raw=raw)

        raw = await r.json()

        self._fire_raw_response(bot, raw)

        if is_return_raw:
            return raw

        model = model(**raw)  # type: ignore

        if hasattr(model, "message"):
            attr = getattr(model, "message")
            if hasattr(attr, "bot"):
                attr.bot = bot

        if hasattr(model, "bot"):
            model.bot = bot  # type: ignore

        return model

    async def _post_form(
        self, url: str, form: FormData
    ) -> str:
        """Отправляет FormData POST-запрос через существующую или временную сессию.

        Args:
            url: URL для загрузки.
            form: Подготовленные данные формы.

        Returns:
            Сырой текстовый ответ от сервера.
        """

        bot = self._ensure_bot()
        session = bot.session

        if session is not None and not session.closed:
            response = await session.post(url=url, data=form)
            return await response.text()

        async with ClientSession() as temp_session:
            response = await temp_session.post(url=url, data=form)
            return await response.text()

    async def upload_file(
        self, url: str, path: str, type: UploadType
    ) -> str:
        """Загружает файл на сервер.

        Args:
            url: URL загрузки.
            path: Путь к файлу.
            type: Тип файла.

        Returns:
            Сырой .text() ответ от сервера.
        """

        async with aiofiles.open(path, "rb") as f:
            file_data = await f.read()

        basename = os.path.basename(path)
        _, ext = os.path.splitext(basename)

        form = FormData(quote_fields=False)
        form.add_field(
            name="data",
            value=file_data,
            filename=basename,
            content_type=f"{type.value}/{ext.lstrip('.')}",
        )

        return await self._post_form(url, form)

    async def upload_file_buffer(
        self,
        filename: str,
        url: str,
        buffer: bytes,
        type: UploadType,
    ) -> str:
        """Загружает файл из буфера.

        Args:
            filename: Имя файла.
            url: URL загрузки.
            buffer: Буфер данных.
            type: Тип файла.

        Returns:
            Сырой .text() ответ от сервера.
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
            logger_connection.debug(
                "Не удалось определить MIME-тип буфера, "
                "используется %s/*",
                type.value,
            )
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

        return await self._post_form(url, form)
