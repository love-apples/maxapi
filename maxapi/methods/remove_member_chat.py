from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from .types.removed_member_chat import RemovedMemberChat

if TYPE_CHECKING:
    from ..bot import Bot


class RemoveMemberChat(BaseConnection):
    """
    Класс для удаления участника из чата с опцией блокировки.

    Attributes:
        bot (Bot): Экземпляр бота для выполнения запроса.
        chat_id (int): Идентификатор чата.
        user_id (int): Идентификатор пользователя, которого необходимо удалить.
        block (bool, optional): Блокировать пользователя после удаления. По умолчанию False.
    """

    def __init__(
        self,
        bot: "Bot",
        chat_id: int,
        user_id: int,
        block: bool = False,
    ):
        self.bot = bot
        self.chat_id = chat_id
        self.user_id = user_id
        self.block = block

    async def fetch(self) -> RemovedMemberChat:
        """
        Выполняет DELETE-запрос для удаления пользователя из чата.

        Параметр `block` определяет, будет ли пользователь заблокирован после удаления.

        Returns:
            RemovedMemberChat: Результат удаления участника.
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        params["chat_id"] = self.chat_id
        params["user_id"] = self.user_id
        params["block"] = str(self.block).lower()

        response = await super().request(
            method=HTTPMethod.DELETE,
            path=ApiPath.CHATS.value
            + "/"
            + str(self.chat_id)
            + ApiPath.MEMBERS,
            model=RemovedMemberChat,
            params=params,
        )

        return cast(RemovedMemberChat, response)
