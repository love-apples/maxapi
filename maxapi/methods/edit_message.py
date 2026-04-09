from __future__ import annotations

import asyncio
import time
import warnings
from typing import TYPE_CHECKING, Any, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..enums.parse_mode import ParseMode, TextFormat
from ..exceptions.max import MaxApiError
from ..loggers import logger_bot
from ..types.attachments.attachment import Attachment
from ..types.attachments.upload import AttachmentUpload
from ..types.input_media import InputMedia, InputMediaBuffer
from ..utils.message import process_input_media
from .types.edited_message import EditedMessage

if TYPE_CHECKING:
    from ..bot import Bot
    from ..types.attachments import Attachments
    from ..types.message import NewMessageLink


class EditMessage(BaseConnection):
    """
    Класс для редактирования существующего сообщения через API.

    https://dev.max.ru/docs-api/methods/PUT/messages

    Attributes:
        bot (Bot): Экземпляр бота для выполнения запроса.
        message_id (str): Идентификатор сообщения для редактирования.
        text (Optional[str]): Новый текст сообщения.
        attachments (List[Attachment | InputMedia | InputMediaBuffer] | None):
            Список вложений для сообщения.
        link (Optional[NewMessageLink]): Связь с другим сообщением
            (например, ответ или пересылка).
        notify (Optional[bool]): Отправлять ли уведомление о сообщении.
            По умолчанию True.
        format (Optional[TextFormat]): Формат разметки текста
            (например, Markdown, HTML).
        parse_mode (Optional[ParseMode]): Устаревший формат разметки текста
            (например, Markdown, HTML).
    """

    def __init__(
        self,
        bot: Bot,
        message_id: str,
        text: str | None = None,
        attachments: list[
            Attachment | InputMedia | InputMediaBuffer | AttachmentUpload
        ]
        | list[Attachments]
        | None = None,
        link: NewMessageLink | None = None,
        format: TextFormat | None = None,
        parse_mode: ParseMode | None = None,
        *,
        notify: bool | None = None,
        sleep_after_input_media: bool | None = True,
    ):
        if text is not None and len(text) >= 4000:
            raise ValueError("text должен быть меньше 4000 символов")

        super().__init__()
        self.bot = bot
        self.message_id = message_id
        self.text = text
        self.attachments = attachments
        self.link = link
        self.notify = notify
        if parse_mode is not None:
            warnings.warn(
                "Параметр parse_mode устарел, используйте format.",
                DeprecationWarning,
                stacklevel=4,
            )
        # Поддержка передачи строки вместо enum для обратной
        # совместимости: пользователь может передать "html" или
        # TextFormat.HTML — внутри всегда храним enum, чтобы .value
        # работал без ошибок.
        if isinstance(format, str) and not isinstance(format, TextFormat):
            format = TextFormat(format)
        if isinstance(parse_mode, str) and not isinstance(
            parse_mode, ParseMode
        ):
            parse_mode = ParseMode(parse_mode)
        self.format: TextFormat | None = (
            format if format is not None else parse_mode
        )
        self.sleep_after_input_media = sleep_after_input_media

    async def fetch(self) -> EditedMessage | None:
        """
        Выполняет PUT-запрос для обновления сообщения.

        Формирует тело запроса на основе переданных параметров и
        отправляет запрос к API.

        Returns:
            EditedMessage: Обновлённое сообщение.
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        json: dict[str, Any] = {"attachments": []}

        params["message_id"] = self.message_id

        if self.text is not None:
            json["text"] = self.text

        has_input_media = False

        if self.attachments:
            for att in self.attachments:
                if isinstance(att, (InputMedia, InputMediaBuffer)):
                    has_input_media = True

                    input_media = await process_input_media(
                        base_connection=self, bot=bot, att=att
                    )
                    json["attachments"].append(input_media.model_dump())
                elif isinstance(att, Attachment) and isinstance(
                    att.payload, AttachmentUpload
                ):
                    json["attachments"].append(att.payload.model_dump())
                else:
                    json["attachments"].append(att.model_dump())

        if self.link is not None:
            json["link"] = self.link.model_dump()
        if self.notify is not None:
            json["notify"] = self.notify
        if self.format is not None:
            json["format"] = self.format.value

        if has_input_media and self.sleep_after_input_media:
            await asyncio.sleep(bot.after_input_media_delay)

        attempts = bot.after_upload_attempts
        retry_delay = bot.after_upload_retry_delay
        give_up_timeout = bot.after_upload_give_up_timeout

        response = None

        start_time = time.monotonic()
        for attempt in range(attempts):
            try:
                response = await super().request(
                    method=HTTPMethod.PUT,
                    path=ApiPath.MESSAGES,
                    model=EditedMessage,
                    params=params,
                    json=json,
                )
            except MaxApiError as e:
                if (
                    isinstance(e.raw, dict)
                    and e.raw.get("code") == "attachment.not.ready"
                ):
                    elapsed = time.monotonic() - start_time
                    if (
                        give_up_timeout is not None
                        and elapsed + retry_delay > give_up_timeout
                    ):
                        raise RuntimeError(
                            f"Превышено максимальное время ожидания"
                            f" готовности медиа"
                            f" ({give_up_timeout}с),"
                            f" прошло {elapsed:.1f}с"
                        ) from e
                    logger_bot.info(
                        f"Ошибка при отправке загруженного медиа,"
                        f" попытка {attempt + 1},"
                        f" жду {retry_delay} секунды"
                    )
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    raise e

            break

        if response is None:
            raise RuntimeError("Не удалось отредактировать сообщение")

        return cast(EditedMessage | None, response)
