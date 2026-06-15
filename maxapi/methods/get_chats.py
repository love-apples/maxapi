import warnings
from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..types.chats import Chats

if TYPE_CHECKING:
    from ..bot import Bot


class GetChats(BaseConnection):
    """
    Класс для получения списка чатов.

    .. deprecated:: 1.1.0
        Начиная с июня 2026 года метод ``GET /chats`` больше не
        поддерживается. API не предоставляет готового способа получить
        список групповых чатов и каналов, в которые добавлен бот.

    https://dev.max.ru/docs-api/methods/GET/chats

    Attributes:
        bot: Инициализированный клиент бота.
        count: Максимальное количество чатов,
            возвращаемых за один запрос.
        marker: Маркер для продолжения пагинации.
    """

    def __init__(
        self,
        bot: "Bot",
        count: int | None = None,
        marker: int | None = None,
    ):
        warnings.warn(
            "GetChats устарел: начиная с июня 2026 года GET /chats "
            "больше не поддерживается. API не предоставляет готового "
            "способа получить список групповых чатов и каналов, "
            "в которые добавлен бот.",
            DeprecationWarning,
            stacklevel=2,
        )

        if count is not None and not (1 <= count <= 100):
            raise ValueError("count не должен быть меньше 1 или больше 100")

        super().__init__()
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

        if self.marker is not None:
            params["marker"] = self.marker

        response = await super().request(
            method=HTTPMethod.GET,
            path=ApiPath.CHATS,
            model=Chats,
            params=params,
        )

        return cast(Chats, response)
