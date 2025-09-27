from __future__ import annotations

import os
import mimetypes

from typing import TYPE_CHECKING, Any, Optional

import aiofiles
import puremagic

from pydantic import BaseModel
from aiohttp import ClientSession, ClientConnectionError, FormData

from ..exceptions.invalid_token import InvalidToken
from ..exceptions.max import MaxConnection

from ..types.errors import Error
from ..enums.http_method import HTTPMethod
from ..enums.api_path import ApiPath
from ..enums.upload_type import UploadType

from ..loggers import logger_bot

if TYPE_CHECKING:
    from ..bot import Bot


class BaseConnection:
    
    """
    Базовый класс для всех методов API.

    Содержит общую логику выполнения запроса (сериализация, отправка HTTP-запроса, обработка ответа).
    """

    API_URL = 'https://platform-api.max.ru'
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
        
        self.bot: Optional[Bot] = None
        self.session: Optional[ClientSession] = None
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
        is_return_raw: bool = False,
        **kwargs: Any
    ) -> Error | Any | BaseModel:
        
        """
        Выполняет HTTP-запрос к API.

        Args:
            method (HTTPMethod): HTTP-метод (GET, POST и т.д.).
            path (ApiPath | str): Путь до конечной точки.
            model (BaseModel | Any, optional): Pydantic-модель для десериализации ответа, если is_return_raw=False.
            is_return_raw (bool, optional): Если True — вернуть сырой ответ, иначе — результат десериализации.
            **kwargs: Дополнительные параметры (query, headers, json).

        Returns:
            model | dict | Error: Объект модели, dict или ошибка.

        Raises:
            RuntimeError: Если бот не инициализирован.
            MaxConnection: Ошибка соединения.
            InvalidToken: Ошибка авторизации (401).
        """
        
        if self.bot is None:
            raise RuntimeError('Bot не инициализирован')

        if not self.bot.session:
            self.bot.session = ClientSession(
                base_url=self.bot.api_url,
                timeout=self.bot.default_connection.timeout,
                headers=self.bot.headers,
                **self.bot.default_connection.kwargs
            )

        try:
            r = await self.bot.session.request(
                method=method.value,
                url=path.value if isinstance(path, ApiPath) else path,
                **kwargs
            )
        except ClientConnectionError as e:
            raise MaxConnection(f'Ошибка при отправке запроса: {e}')

        if r.status == 401:
            await self.bot.session.close()
            raise InvalidToken('Неверный токен!')

        if not r.ok:
            raw = await r.json()
            error = Error(code=r.status, raw=raw)
            logger_bot.error(error)
            return error

        raw = await r.json()

        if is_return_raw:
            return raw

        model = model(**raw)  # type: ignore

        if hasattr(model, 'message'):
            attr = getattr(model, 'message')
            if hasattr(attr, 'bot'):
                attr.bot = self.bot

        if hasattr(model, 'bot'):
            model.bot = self.bot

        return model

    async def upload_file(
        self,
        url: str,
        path: str,
        type: UploadType
    ):
        
        """
        Загружает файл на сервер.

        Args:
            url (str): URL загрузки.
            path (str): Путь к файлу.
            type (UploadType): Тип файла.

        Returns:
            str: Сырой .text() ответ от сервера.
        """
        
        async with aiofiles.open(path, 'rb') as f:
            file_data = await f.read()

        basename = os.path.basename(path)
        _, ext = os.path.splitext(basename)

        form = FormData()
        form.add_field(
            name='data',
            value=file_data,
            filename=basename,
            content_type=f"{type.value}/{ext.lstrip('.')}"
        )

        async with ClientSession() as session:
            response = await session.post(
                url=url,
                data=form
            )

            return await response.text()

    async def upload_file_buffer(
        self,
        filename: str,
        url: str,
        buffer: bytes,
        type: UploadType
    ):
        
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
                ext = mimetypes.guess_extension(mime_type) or ''
            else:
                mime_type = f"{type.value}/*"
                ext = ''
        except Exception:
            mime_type = f"{type.value}/*"
            ext = ''

        basename = f'{filename}{ext}'

        form = FormData()
        form.add_field(
            name='data',
            value=buffer,
            filename=basename,
            content_type=mime_type
        )

        async with ClientSession() as session:
            response = await session.post(
                url=url,
                data=form
            )
            return await response.text()