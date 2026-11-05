import warnings
from typing import TYPE_CHECKING, Any, cast

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
    После вызова этого метода бот будет получать уведомления о новых
    событиях в чатах на указанный URL.

    .. warning::
        MAX принимает webhook только по HTTPS на порту 443. Нужен
        сертификат от доверенного центра сертификации или Минцифры;
        HTTP и самоподписные сертификаты не поддерживаются.

    Attributes:
        bot: Экземпляр бота для выполнения запроса.
        url: HTTPS-эндпойнт вашего бота на порту 443.
        update_types: Список типов обновлений,
            которые ваш бот хочет получать. Для полного списка типов
            см. объект
        secret: От 5 до 256 символов. Секрет, который
            должен быть отправлен в заголовке X-Max-Bot-Api-Secret в
            каждом запросе Webhook. Разрешены символы A-Z, a-z, 0-9,
            подчёркивание и дефис. Заголовок рекомендован, чтобы запрос
            поступал из установленного веб-узла
    """

    def __init__(
        self,
        bot: "Bot",
        url: str,
        update_types: list[UpdateType] | None = None,
        secret: str | None = None,
    ):
        if secret is not None and not (5 <= len(secret) <= 256):
            raise ValueError(
                "secret не должен быть меньше 5 или больше 256 символов"
            )

        if url.startswith("http://"):
            warnings.warn(
                "URL вебхука не использует HTTPS. "
                "Обновления будут передаваться по незашифрованному каналу.",
                stacklevel=2,
            )

        super().__init__()
        self.bot = bot
        self.url = url
        self.update_types = update_types
        self.secret = secret

    async def fetch(self) -> Subscribed:
        """
        Отправляет запрос на подписку бота на получение обновлений
        через WebHook.

        Returns:
            Subscribed: Объект с информацией об операции
        """

        bot = self._ensure_bot()

        json: dict[str, Any] = {}

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
