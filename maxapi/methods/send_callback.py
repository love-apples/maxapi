from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..methods.types.sended_callback import SendedCallback

if TYPE_CHECKING:
    from ..bot import Bot
    from ..types.updates.message_callback import MessageForCallback


class SendCallback(BaseConnection):
    """
    Класс для отправки callback-ответа с опциональным сообщением и уведомлением.

    https://dev.max.ru/docs-api/methods/POST/answers

    Attributes:
        bot (Bot): Экземпляр бота.
        callback_id (str): Идентификатор callback.
        message (Optional[MessageForCallback]): Сообщение для отправки.
        notification (Optional[str]): Текст уведомления.
    """

    def __init__(
        self,
        bot: "Bot",
        callback_id: str,
        message: Optional[MessageForCallback] = None,
        notification: Optional[str] = None,
    ):
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

        json: Dict[str, Any] = {}

        if self.message:
            json["message"] = self.message.model_dump()
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
