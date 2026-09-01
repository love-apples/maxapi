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
        поддерживается. Готового списка чатов API не отдаёт ни
        через Long Polling, ни через Webhook — его нужно
        накапливать из событий.

    Рекомендованный сценарий замены — накапливать ``chat_id``
    самостоятельно:

    1. Получайте события ``bot_added``, ``bot_started`` и
       ``bot_removed`` — через Long Polling (хендлеры
       ``@dp.bot_added()`` и другие при ``dp.start_polling()``)
       или через Webhook (``bot.subscribe_webhook(url,
       update_types=[UpdateType.BOT_ADDED,
       UpdateType.BOT_STARTED, UpdateType.BOT_REMOVED])``).
    2. Извлекайте ``chat_id`` из входящих событий ``bot_added``
       и ``bot_started``.
    3. Храните ``chat_id`` самостоятельно: сохраняйте при
       получении события, учитывайте возможные дубли и удаляйте
       по ``bot_removed`` (для диалогов — по ``bot_stopped``).
    4. Используйте накопленные ``chat_id`` в остальных методах
       API, например ``bot.send_message()``.

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
            "GetChats устарел: начиная с июня 2026 года GET /chats не "
            "поддерживается — https://dev.max.ru/docs-api/methods/GET/chats. "
            "Ведите список чатов сами по событиям bot_added, bot_started и "
            "bot_removed (Long Polling или subscribe_webhook()).",
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
