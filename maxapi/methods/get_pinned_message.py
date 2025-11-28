from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from .types.getted_pineed_message import GettedPin

if TYPE_CHECKING:
    from ..bot import Bot


class GetPinnedMessage(BaseConnection):
    """
    Класс для получения закреплённого сообщения в указанном чате.

    https://dev.max.ru/docs-api/methods/GET/chats/-chatId-/pin

    Attributes:
        bot (Bot): Экземпляр бота для выполнения запроса.
        chat_id (int): Идентификатор чата.
    """

    def __init__(
        self,
        bot: "Bot",
        chat_id: int,
    ):
        self.bot = bot
        self.chat_id = chat_id

    async def fetch(self) -> GettedPin:
        """
        Выполняет GET-запрос для получения закреплённого сообщения.

        Returns:
            GettedPin: Объект с информацией о закреплённом сообщении.
        """

        bot = self._ensure_bot()

        response = await super().request(
            method=HTTPMethod.GET,
            path=ApiPath.CHATS + "/" + str(self.chat_id) + ApiPath.PIN,
            model=GettedPin,
            params=bot.params,
        )

        return cast(GettedPin, response)
