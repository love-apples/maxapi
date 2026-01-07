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
from .types.sended_message import SendedMessage

if TYPE_CHECKING:
    from ..bot import Bot


class SendMessage(BaseConnection):
    """
    Класс для отправки сообщения в чат или пользователю с поддержкой вложений и форматирования.

    https://dev.max.ru/docs-api/methods/POST/messages

    Attributes:
        bot (Bot): Экземпляр бота для выполнения запроса.
        chat_id (Optional[int]): Идентификатор чата, куда отправлять сообщение.
        user_id (Optional[int]): Идентификатор пользователя, если нужно отправить личное сообщение.
        text (Optional[str]): Текст сообщения.
        attachments (Optional[List[Attachment | InputMedia | InputMediaBuffer]]):
            Список вложений к сообщению.
        link (Optional[NewMessageLink]): Связь с другим сообщением (например, ответ или пересылка).
        notify (Optional[bool]): Отправлять ли уведомление о сообщении. По умолчанию True.
        parse_mode (Optional[ParseMode]): Режим разбора текста (например, Markdown, HTML).
        disable_link_preview (Optional[bool]): Флаг генерации превью.
    """

    def __init__(
        self,
        bot: "Bot",
        chat_id: Optional[int] = None,
        user_id: Optional[int] = None,
        text: Optional[str] = None,
        attachments: Optional[
            List[Attachment | InputMedia | InputMediaBuffer]
            | List[Attachments]
        ] = None,
        link: Optional[NewMessageLink] = None,
        notify: Optional[bool] = None,
        parse_mode: Optional[ParseMode] = None,
        disable_link_preview: Optional[bool] = None,
        sleep_after_input_media: Optional[bool] = True,
    ):
        if text is not None and not (len(text) < 4000):
            raise ValueError("text должен быть меньше 4000 символов")

        self.bot = bot
        self.chat_id = chat_id
        self.user_id = user_id
        self.text = text
        self.attachments = attachments
        self.link = link
        self.notify = notify
        self.parse_mode = parse_mode
        self.disable_link_preview = disable_link_preview
        self.sleep_after_input_media = sleep_after_input_media

    async def fetch(self) -> Optional[SendedMessage]:
        """
        Отправляет сообщение с вложениями (если есть), с обработкой задержки готовности вложений.

        Возвращает результат отправки или ошибку.

        Возвращаемое значение:
            SendedMessage или Error
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        json: Dict[str, Any] = {"attachments": []}

        if self.chat_id:
            params["chat_id"] = self.chat_id
        elif self.user_id:
            params["user_id"] = self.user_id

        json["text"] = self.text

        HAS_INPUT_MEDIA = False

        if self.attachments:
            for att in self.attachments:
                if isinstance(att, (InputMedia, InputMediaBuffer)):
                    HAS_INPUT_MEDIA = True

                    input_media = await process_input_media(
                        base_connection=self, bot=bot, att=att
                    )
                    json["attachments"].append(input_media.model_dump())
                else:
                    json["attachments"].append(att.model_dump())

        if self.link is not None:
            json["link"] = self.link.model_dump()

        if self.notify:
            json["notify"] = self.notify

        if self.disable_link_preview:
            json["disable_link_preview"] = self.disable_link_preview

        if self.parse_mode is not None:
            json["format"] = self.parse_mode.value

        if HAS_INPUT_MEDIA and self.sleep_after_input_media:
            await asyncio.sleep(bot.after_input_media_delay)

        response = None
        for attempt in range(self.ATTEMPTS_COUNT):
            try:
                response = await super().request(
                    method=HTTPMethod.POST,
                    path=ApiPath.MESSAGES,
                    model=SendedMessage,
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
                else:
                    raise e

            break

        if response is None:
            raise RuntimeError("Не удалось отправить сообщение")

        return cast(Optional[SendedMessage], response)
