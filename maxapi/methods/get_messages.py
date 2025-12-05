from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Union, cast

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
        bot (Bot): Экземпляр бота.
        chat_id (int): Идентификатор чата.
        message_ids (List[str] | None): Фильтр по идентификаторам сообщений.
        from_time (datetime | int | None): Начальная временная метка.
        to_time (datetime | int | None): Конечная временная метка.
        count (int): Максимальное число сообщений.
    """

    def __init__(
        self,
        bot: "Bot",
        chat_id: Optional[int] = None,
        message_ids: Optional[List[str]] = None,
        from_time: Optional[Union[datetime, int]] = None,
        to_time: Optional[Union[datetime, int]] = None,
        count: int = 50,
    ):
        if count is not None and not (1 <= count <= 100):
            raise ValueError("count не должен быть меньше 1 или больше 100")

        self.bot = bot
        self.chat_id = chat_id
        self.message_ids = message_ids
        self.from_time = from_time
        self.to_time = to_time
        self.count = count

    async def fetch(self) -> Messages:
        """
        Выполняет GET-запрос для получения сообщений с учётом параметров фильтрации.

        Преобразует datetime в UNIX timestamp при необходимости.

        Returns:
            Messages: Объект с полученными сообщениями.
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        if self.chat_id:
            params["chat_id"] = self.chat_id

        if self.message_ids:
            params["message_ids"] = ",".join(self.message_ids)

        if self.from_time:
            if isinstance(self.from_time, datetime):
                params["from"] = int(self.from_time.timestamp() * 1000)
            else:
                params["from"] = self.from_time

        if self.to_time:
            if isinstance(self.to_time, datetime):
                params["to"] = int(self.to_time.timestamp() * 1000)
            else:
                params["to"] = self.to_time

        params["count"] = self.count

        response = await super().request(
            method=HTTPMethod.GET,
            path=ApiPath.MESSAGES,
            model=Messages,
            params=params,
        )

        return cast(Messages, response)
