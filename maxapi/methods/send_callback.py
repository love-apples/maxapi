from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..methods.types.sended_callback import SendedCallback
from ..types.attachments.attachment import Attachment
from ..types.attachments.upload import AttachmentUpload
from ..types.input_media import InputMedia, InputMediaBuffer
from ..utils.message import process_input_media

if TYPE_CHECKING:
    from ..bot import Bot
    from ..types.updates.message_callback import MessageForCallback


class SendCallback(BaseConnection):
    """
    Класс для отправки callback-ответа с опциональным сообщением
    и уведомлением.

    https://dev.max.ru/docs-api/methods/POST/answers

    Attributes:
        bot: Экземпляр бота.
        callback_id: Идентификатор callback.
        message: Сообщение для отправки. Может быть None.
        notification: Текст уведомления. Может быть None.
    """

    def __init__(
        self,
        bot: Bot,
        callback_id: str,
        message: MessageForCallback | None = None,
        notification: str | None = None,
    ):
        super().__init__()
        self.bot = bot
        self.callback_id = callback_id
        self.message = message
        self.notification = notification

    async def fetch(self) -> SendedCallback:
        """
        Выполняет POST-запрос для отправки callback-ответа.

        Возвращает результат отправки.

        Returns:
            SendedCallback: Объект с результатом отправки callback.
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        params["callback_id"] = self.callback_id

        json: dict[str, Any] = {}

        if self.message:
            message_json = self.message.model_dump(
                exclude={"attachments"},
                exclude_none=True,
            )
            if self.message.attachments is not None:
                message_json["attachments"] = []
                for att in self.message.attachments:
                    if isinstance(att, InputMedia | InputMediaBuffer):
                        input_media = await process_input_media(
                            base_connection=self,
                            bot=bot,
                            att=att,
                        )
                        message_json["attachments"].append(
                            input_media.model_dump()
                        )
                    elif isinstance(att, Attachment) and isinstance(
                        att.payload, AttachmentUpload
                    ):
                        message_json["attachments"].append(
                            {
                                "type": att.type,
                                "payload": att.payload.payload.model_dump(),
                            }
                        )
                    else:
                        message_json["attachments"].append(att.model_dump())

            json["message"] = message_json
        if self.notification:
            json["notification"] = self.notification

        response = await super().request(
            method=HTTPMethod.POST,
            path=ApiPath.ANSWERS,
            model=SendedCallback,
            params=params,
            json=json,
        )

        return cast(SendedCallback, response)
