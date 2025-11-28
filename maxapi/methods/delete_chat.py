from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..methods.types.deleted_chat import DeletedChat

if TYPE_CHECKING:
    from ..bot import Bot


class DeleteChat(BaseConnection):
    """
    Класс для удаления чата через API.

    https://dev.max.ru/docs-api/methods/DELETE/chats/-chatId-

    Attributes:
        bot (Bot): Экземпляр бота для выполнения запроса.
        chat_id (int): Идентификатор чата, который необходимо удалить.
    """

    def __init__(self, bot: "Bot", chat_id: int):
        self.bot = bot
        self.chat_id = chat_id

    async def fetch(self) -> DeletedChat:
        """
        Отправляет DELETE-запрос для удаления указанного чата.

        Returns:
            DeletedChat: Результат операции удаления чата.
        """

        bot = self._ensure_bot()

        response = await super().request(
            method=HTTPMethod.DELETE,
            path=ApiPath.CHATS.value + "/" + str(self.chat_id),
            model=DeletedChat,
            params=bot.params,
        )

        return cast(DeletedChat, response)
