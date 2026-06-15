from datetime import datetime
from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..types.message import Messages

if TYPE_CHECKING:
    from ..bot import Bot


class GetMessages(BaseConnection):
    """
    Класс для получения сообщений из чата через API.

    https://dev.max.ru/docs-api/methods/GET/messages

    Attributes:
        bot: Экземпляр бота.
        chat_id: Идентификатор чата.
        message_ids: Фильтр по идентификаторам сообщений.
        from_time: Начальная временная метка.
        to_time: Конечная временная метка.
        count: Максимальное число сообщений.
    """

    def __init__(
        self,
        bot: "Bot",
        chat_id: int | None = None,
        message_ids: list[str] | None = None,
        from_time: datetime | int | None = None,
        to_time: datetime | int | None = None,
        count: int | None = 50,
    ):
        if count is not None and not (1 <= count <= 100):
            raise ValueError("count не должен быть меньше 1 или больше 100")

        has_chat_id = chat_id is not None
        has_message_ids = bool(message_ids)
        if has_chat_id == has_message_ids:
            raise ValueError(
                "Нужно передать ровно один из параметров: "
                "chat_id или message_ids"
            )

        super().__init__()
        self.bot = bot
        self.chat_id = chat_id
        self.message_ids = message_ids
        self.from_time = from_time
        self.to_time = to_time
        self.count = count

    async def fetch(self) -> Messages:
        """
        Выполняет GET-запрос для получения сообщений с учётом
        параметров фильтрации.

        Преобразует datetime в UNIX timestamp при необходимости.

        Returns:
            Messages: Объект с полученными сообщениями.
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        if self.chat_id is not None:
            params["chat_id"] = self.chat_id

        if self.message_ids:
            params["message_ids"] = ",".join(self.message_ids)

        if self.from_time is not None:
            if isinstance(self.from_time, datetime):
                params["from"] = int(self.from_time.timestamp())
            else:
                params["from"] = self.from_time

        if self.to_time is not None:
            if isinstance(self.to_time, datetime):
                params["to"] = int(self.to_time.timestamp())
            else:
                params["to"] = self.to_time

        if self.count is not None:
            params["count"] = self.count

        response = await super().request(
            method=HTTPMethod.GET,
            path=ApiPath.MESSAGES,
            model=Messages,
            params=params,
        )

        return cast(Messages, response)
