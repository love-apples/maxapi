from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..enums.update import UpdateType
from ..methods.types.subscribed import Subscribed

if TYPE_CHECKING:
    from ..bot import Bot


class SubscribeWebhook(BaseConnection):
    """
    Подписывает бота на получение обновлений через WebHook.
    После вызова этого метода бот будет получать уведомления о новых событиях в чатах на указанный URL.
    Ваш сервер должен прослушивать один из следующих портов: `80`, `8080`, `443`, `8443`, `16384`-`32383`.

    Attributes:
        bot (Bot): Экземпляр бота для выполнения запроса.
        url (str): URL HTTP(S)-эндпойнта вашего бота. Должен начинаться с http(s)://
        update_types (Optional[List[str]]): Список типов обновлений, которые ваш бот хочет получать. Для полного списка типов см. объект
        secret (Optional[str]): От 5 до 256 символов. Cекрет, который должен быть отправлен в заголовке X-Max-Bot-Api-Secret в каждом запросе Webhook.
            Разрешены только символы A-Z, a-z, 0-9, и дефис. Заголовок рекомендован, чтобы запрос поступал из установленного веб-узла
    """

    def __init__(
        self,
        bot: "Bot",
        url: str,
        update_types: Optional[List[UpdateType]] = None,
        secret: Optional[str] = None,
    ):
        if secret is not None and not (5 <= len(secret) <= 256):
            raise ValueError(
                "secret не должен быть меньше 5 или больше 256 символов"
            )

        self.bot = bot
        self.url = url
        self.update_types = update_types
        self.secret = secret

    async def fetch(self) -> Subscribed:
        """
        Отправляет запрос на подписку бота на получение обновлений через WebHook

        Returns:
            Subscribed: Объект с информацией об операции
        """

        bot = self._ensure_bot()

        json: Dict[str, Any] = {}

        json["url"] = self.url

        if self.update_types:
            json["update_types"] = self.update_types

        if self.secret:
            json["secret"] = self.secret

        response = await super().request(
            method=HTTPMethod.POST,
            path=ApiPath.SUBSCRIPTIONS,
            model=Subscribed,
            params=bot.params,
            json=json,
        )

        return cast(Subscribed, response)
