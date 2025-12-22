from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..enums.parse_mode import ParseMode
from ..exceptions.max import MaxApiError
from ..loggers import logger_bot
from ..types.attachments import Attachments
from ..types.attachments.attachment import Attachment
from ..types.input_media import InputMedia, InputMediaBuffer
from ..types.message import NewMessageLink
from ..utils.message import process_input_media
from .types.edited_message import EditedMessage

if TYPE_CHECKING:
    from ..bot import Bot


class EditMessage(BaseConnection):
    """
    Класс для редактирования существующего сообщения через API.

    https://dev.max.ru/docs-api/methods/PUT/messages

    Attributes:
        bot (Bot): Экземпляр бота для выполнения запроса.
        message_id (str): Идентификатор сообщения для редактирования.
        text (Optional[str]): Новый текст сообщения.
        attachments (Optional[List[Attachment | InputMedia | InputMediaBuffer]]):
            Список вложений для сообщения.
        link (Optional[NewMessageLink]): Связь с другим сообщением (например, ответ или пересылка).
        notify (Optional[bool]): Отправлять ли уведомление о сообщении. По умолчанию True.
        parse_mode (Optional[ParseMode]): Формат разметки текста (например, Markdown, HTML).
    """

    def __init__(
        self,
        bot: Bot,
        message_id: str,
        text: Optional[str] = None,
        attachments: Optional[
            List[Attachment | InputMedia | InputMediaBuffer]
            | List[Attachments]
        ] = None,
        link: Optional[NewMessageLink] = None,
        notify: Optional[bool] = None,
        parse_mode: Optional[ParseMode] = None,
        sleep_after_input_media: Optional[bool] = True,
    ):
        if text is not None and not (len(text) < 4000):
            raise ValueError("text должен быть меньше 4000 символов")

        self.bot = bot
        self.message_id = message_id
        self.text = text
        self.attachments = attachments
        self.link = link
        self.notify = notify
        self.parse_mode = parse_mode
        self.sleep_after_input_media = sleep_after_input_media

    async def fetch(self) -> Optional[EditedMessage]:
        """
        Выполняет PUT-запрос для обновления сообщения.

        Формирует тело запроса на основе переданных параметров и отправляет запрос к API.

        Returns:
            EditedMessage: Обновлённое сообщение.
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        json: Dict[str, Any] = {"attachments": []}

        params["message_id"] = self.message_id

        if self.text is not None:
            json["text"] = self.text

        HAS_INPUT_MEDIA = False

        if self.attachments:
            for att in self.attachments:
                if isinstance(att, InputMedia) or isinstance(
                    att, InputMediaBuffer
                ):
                    HAS_INPUT_MEDIA = True

                    input_media = await process_input_media(
                        base_connection=self, bot=bot, att=att
                    )
                    json["attachments"].append(input_media.model_dump())
                else:
                    json["attachments"].append(att.model_dump())

        if self.link is not None:
            json["link"] = self.link.model_dump()
        if self.notify is not None:
            json["notify"] = self.notify
        if self.parse_mode is not None:
            json["format"] = self.parse_mode.value

        if HAS_INPUT_MEDIA and self.sleep_after_input_media:
            await asyncio.sleep(bot.after_input_media_delay)

        response = None

        for attempt in range(self.ATTEMPTS_COUNT):
            try:
                response = await super().request(
                    method=HTTPMethod.PUT,
                    path=ApiPath.MESSAGES,
                    model=EditedMessage,
                    params=params,
                    json=json,
                )
            except MaxApiError as e:
                if "attachment.not.ready" in e.raw:
                    logger_bot.info(
                        f"Ошибка при отправке загруженного медиа, попытка {attempt + 1}, жду {self.RETRY_DELAY} секунды"
                    )
                    await asyncio.sleep(self.RETRY_DELAY)
                    continue

            break

        if response is None:
            raise RuntimeError("Не удалось отредактировать сообщение")

        return cast(Optional[EditedMessage], response)
