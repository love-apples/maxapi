from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..methods.types.getted_subscriptions import GettedSubscriptions

if TYPE_CHECKING:
    from ..bot import Bot


class GetSubscriptions(BaseConnection):
    """
    Если ваш бот получает данные через WebHook, этот класс возвращает список всех подписок.

    https://dev.max.ru/docs-api/methods/GET/subscriptions

    Attributes:
        bot (Bot): Экземпляр бота
    """

    def __init__(
        self,
        bot: "Bot",
    ):
        self.bot = bot

    async def fetch(self) -> GettedSubscriptions:
        """
        Отправляет запрос на получение списка всех подписок.

        Returns:
            GettedSubscriptions: Объект со списком подписок
        """

        bot = self._ensure_bot()

        response = await super().request(
            method=HTTPMethod.GET,
            path=ApiPath.SUBSCRIPTIONS,
            model=GettedSubscriptions,
            params=bot.params,
        )

        return cast(GettedSubscriptions, response)
