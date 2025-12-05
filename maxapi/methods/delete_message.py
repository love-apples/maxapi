from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..methods.types.deleted_message import DeletedMessage

if TYPE_CHECKING:
    from ..bot import Bot


class DeleteMessage(BaseConnection):
    """
    Класс для удаления сообщения через API.

    https://dev.max.ru/docs-api/methods/DELETE/messages

    Attributes:
        bot (Bot): Экземпляр бота для выполнения запроса.
        message_id (str): Идентификатор сообщения, которое нужно удалить.
    """

    def __init__(
        self,
        bot: "Bot",
        message_id: str,
    ):
        if len(message_id) < 1:
            raise ValueError("message_id не должен быть меньше 1 символа")

        self.bot = bot
        self.message_id = message_id

    async def fetch(self) -> DeletedMessage:
        """
        Выполняет DELETE-запрос для удаления сообщения.

        Использует параметр message_id для идентификации сообщения.

        Returns:
            DeletedMessage: Результат операции удаления сообщения.
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        params["message_id"] = self.message_id

        response = await super().request(
            method=HTTPMethod.DELETE,
            path=ApiPath.MESSAGES,
            model=DeletedMessage,
            params=params,
        )

        return cast(DeletedMessage, response)
