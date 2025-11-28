from typing import TYPE_CHECKING, Any, Dict, List, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..methods.types.added_members_chat import AddedMembersChat

if TYPE_CHECKING:
    from ..bot import Bot


class AddMembersChat(BaseConnection):
    """
    Класс для добавления участников в чат через API.

    https://dev.max.ru/docs-api/methods/POST/chats/-chatId-/members

    Attributes:
        bot (Bot): Экземпляр бота, через который выполняется запрос.
        chat_id (int): Идентификатор целевого чата.
        user_ids (List[int]): Список ID пользователей для добавления в чат.
    """

    def __init__(
        self,
        bot: "Bot",
        chat_id: int,
        user_ids: List[int],
    ):
        self.bot = bot
        self.chat_id = chat_id
        self.user_ids = user_ids

    async def fetch(self) -> AddedMembersChat:
        """
        Отправляет POST-запрос на добавление пользователей в чат.

        Формирует JSON с ID пользователей и вызывает базовый метод запроса.

        Returns:
            AddedMembersChat: Результат операции с информацией об успешности добавления.
        """

        bot = self._ensure_bot()

        json: Dict[str, Any] = {}

        json["user_ids"] = self.user_ids

        response = await super().request(
            method=HTTPMethod.POST,
            path=ApiPath.CHATS.value
            + "/"
            + str(self.chat_id)
            + ApiPath.MEMBERS,
            model=AddedMembersChat,
            params=bot.params,
            json=json,
        )

        return cast(AddedMembersChat, response)
