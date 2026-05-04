import asyncio
import time
import warnings
from typing import TYPE_CHECKING, Any, cast

from ..connection.base import BaseConnection
from ..enums.attachment import AttachmentType
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..enums.parse_mode import ParseMode, TextFormat
from ..exceptions.max import MaxApiError
from ..loggers import logger_bot
from ..types.attachments import Attachments
from ..types.attachments.attachment import Attachment, ButtonsPayload
from ..types.attachments.upload import AttachmentUpload
from ..types.input_media import InputMedia, InputMediaBuffer
from ..types.message import NewMessageLink
from ..utils.message import process_input_media
from .types.sended_message import SendedMessage

if TYPE_CHECKING:
    from ..bot import Bot


class SendMessage(BaseConnection):
    """
    Класс для отправки сообщения в чат или пользователю с поддержкой
    вложений и форматирования.

    https://dev.max.ru/docs-api/methods/POST/messages

    Attributes:
        bot: Экземпляр бота для выполнения запроса.
        chat_id: Идентификатор чата, куда отправлять
            сообщение.
        user_id: Идентификатор пользователя, если нужно
            отправить личное сообщение.
        text: Текст сообщения.
        attachments: Список вложений к сообщению.
            Может быть None.
        link: Связь с другим сообщением
            (например, ответ или пересылка).
        notify: Отправлять ли уведомление о сообщении.
            По умолчанию True.
        format: Режим форматирования
            (например, Markdown, HTML).
        parse_mode: Режим форматирования текста
            (например, Markdown, HTML).
        disable_link_preview: Флаг генерации превью.
    """

    def __init__(
        self,
        bot: "Bot",
        chat_id: int | None = None,
        user_id: int | None = None,
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
        disable_link_preview: bool | None = None,
        sleep_after_input_media: bool | None = True,
    ):
        if text is not None and not (len(text) < 4000):
            raise ValueError("text должен быть меньше 4000 символов")

        super().__init__()
        self.bot = bot
        self.chat_id = chat_id
        self.user_id = user_id
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
        self.disable_link_preview = disable_link_preview
        self.sleep_after_input_media = sleep_after_input_media

    async def fetch(self) -> SendedMessage | None:
        """
        Отправляет сообщение с вложениями (если есть),
        с обработкой задержки готовности вложений.

        Возвращает результат отправки или ошибку.

        Возвращаемое значение:
            SendedMessage или Error
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        json: dict[str, Any] = {"attachments": []}

        if self.chat_id:
            params["chat_id"] = self.chat_id
        elif self.user_id:
            params["user_id"] = self.user_id

        if self.disable_link_preview is not None:
            params["disable_link_preview"] = str(
                self.disable_link_preview
            ).lower()

        if self.text is not None:
            json["text"] = self.text

        has_input_media = False

        if self.attachments:
            for att in self.attachments:
                if (
                    isinstance(att, Attachment)
                    and att.type == AttachmentType.INLINE_KEYBOARD
                    and isinstance(att.payload, ButtonsPayload)
                    and not any(att.payload.buttons)
                ):
                    continue

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
            json["format"] = self.format

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
                    method=HTTPMethod.POST,
                    path=ApiPath.MESSAGES,
                    model=SendedMessage,
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
            raise RuntimeError("Не удалось отправить сообщение")

        return cast(SendedMessage | None, response)
