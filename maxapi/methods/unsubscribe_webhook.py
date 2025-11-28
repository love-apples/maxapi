from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..methods.types.unsubscribed import Unsubscribed

if TYPE_CHECKING:
    from ..bot import Bot


class UnsubscribeWebhook(BaseConnection):
    """
    Отписывает бота от получения обновлений через WebHook.
    После вызова этого метода бот перестает получать уведомления о новых событиях,
    и доступна доставка уведомлений через API с длительным опросом.

    https://dev.max.ru/docs-api/methods/DELETE/subscriptions

    Attributes:
        bot (Bot): Экземпляр бота для выполнения запроса.
        url (str): URL, который нужно удалить из подписок на WebHook
    """

    def __init__(
        self,
        bot: "Bot",
        url: str,
    ):
        self.bot = bot
        self.url = url

    async def fetch(self) -> Unsubscribed:
        """
        Отправляет запрос на подписку бота на получение обновлений через WebHook

        Returns:
            Unsubscribed: Объект с информацией об операции
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        params["url"] = self.url

        response = await super().request(
            method=HTTPMethod.DELETE,
            path=ApiPath.SUBSCRIPTIONS,
            model=Unsubscribed,
            params=params,
        )

        return cast(Unsubscribed, response)
