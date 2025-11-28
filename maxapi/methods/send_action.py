from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..enums.sender_action import SenderAction
from ..methods.types.sended_action import SendedAction

if TYPE_CHECKING:
    from ..bot import Bot


class SendAction(BaseConnection):
    """
    Класс для отправки действия пользователя (например, индикатора печати) в чат.

    https://dev.max.ru/docs-api/methods/POST/chats/-chatId-/actions

    Attributes:
        bot (Bot): Экземпляр бота для выполнения запроса.
        chat_id (Optional[int]): Идентификатор чата. Если None, действие не отправляется.
        action (Optional[SenderAction]): Тип действия. По умолчанию SenderAction.TYPING_ON.
    """

    def __init__(
        self,
        bot: "Bot",
        chat_id: Optional[int] = None,
        action: SenderAction = SenderAction.TYPING_ON,
    ):
        self.bot = bot
        self.chat_id = chat_id
        self.action = action

    async def fetch(self) -> SendedAction:
        """
        Выполняет POST-запрос для отправки действия в указанный чат.

        Returns:
            SendedAction: Результат выполнения запроса.
        """

        bot = self._ensure_bot()

        json: Dict[str, Any] = {}

        json["action"] = self.action.value

        response = await super().request(
            method=HTTPMethod.POST,
            path=ApiPath.CHATS + "/" + str(self.chat_id) + ApiPath.ACTIONS,
            model=SendedAction,
            params=bot.params,
            json=json,
        )

        return cast(SendedAction, response)
