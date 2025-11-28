from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from .types.removed_admin import RemovedAdmin

if TYPE_CHECKING:
    from ..bot import Bot


class RemoveAdmin(BaseConnection):
    """
    Класс для отмены прав администратора в чате.

    https://dev.max.ru/docs-api/methods/DELETE/chats/-chatId-/members/admins/-userId-

    Attributes:
        bot (Bot): Экземпляр бота.
        chat_id (int): Идентификатор чата.
        user_id (int): Идентификатор пользователя.
    """

    def __init__(self, bot: "Bot", chat_id: int, user_id: int):
        self.bot = bot
        self.chat_id = chat_id
        self.user_id = user_id

    async def fetch(self) -> RemovedAdmin:
        """
        Выполняет DELETE-запрос для отмены прав администратора в чате.

        Returns:
            RemovedAdmin: Объект с результатом отмены прав администратора.
        """

        bot = self._ensure_bot()

        response = await super().request(
            method=HTTPMethod.DELETE,
            path=ApiPath.CHATS
            + "/"
            + str(self.chat_id)
            + ApiPath.MEMBERS
            + ApiPath.ADMINS
            + "/"
            + str(self.user_id),
            model=RemovedAdmin,
            params=bot.params,
        )

        return cast(RemovedAdmin, response)
