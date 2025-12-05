from typing import TYPE_CHECKING, Optional, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..types.chats import Chats

if TYPE_CHECKING:
    from ..bot import Bot


class GetChats(BaseConnection):
    """
    Класс для получения списка чатов.

    https://dev.max.ru/docs-api/methods/GET/chats

    Attributes:
        bot (Bot): Инициализированный клиент бота.
        count (Optional[int]): Максимальное количество чатов, возвращаемых за один запрос.
        marker (Optional[int]): Маркер для продолжения пагинации.
    """

    def __init__(
        self,
        bot: "Bot",
        count: Optional[int] = None,
        marker: Optional[int] = None,
    ):
        if count is not None and not (1 <= count <= 100):
            raise ValueError("count не должен быть меньше 1 или больше 100")

        self.bot = bot
        self.count = count
        self.marker = marker

    async def fetch(self) -> Chats:
        """
        Выполняет GET-запрос для получения списка чатов.

        Returns:
            Chats: Объект с данными по списку чатов.
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        if self.count:
            params["count"] = self.count

        if self.marker:
            params["marker"] = self.marker

        response = await super().request(
            method=HTTPMethod.GET,
            path=ApiPath.CHATS,
            model=Chats,
            params=params,
        )

        return cast(Chats, response)
