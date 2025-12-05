from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Sequence, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..enums.update import UpdateType

if TYPE_CHECKING:
    from ..bot import Bot


class GetUpdates(BaseConnection):
    """
    Класс для получения обновлений (updates) от API.

    https://dev.max.ru/docs-api/methods/GET/updates

    Запрашивает новые события для бота через long polling
    с возможностью фильтрации по типам и маркеру последнего обновления.

    Attributes:
        bot (Bot): Экземпляр бота.
        limit (int): Лимит на количество получаемых обновлений.
        timeout (int): Таймаут ожидания.
        marker (Optional[int]): ID последнего обработанного события.
        types (Optional[Sequence[UpdateType]]): Список типов событий для фильтрации.
    """

    def __init__(
        self,
        bot: Bot,
        limit: Optional[int],
        timeout: Optional[int],
        marker: Optional[int] = None,
        types: Optional[Sequence[UpdateType]] = None,
    ):
        if limit is not None and not (1 <= limit <= 1000):
            raise ValueError("limit не должен быть меньше 1 и больше 1000")

        if timeout is not None and not (0 <= timeout <= 90):
            raise ValueError("timeout не должен быть меньше 0 и больше 90")

        self.bot = bot
        self.limit = limit
        self.timeout = timeout
        self.marker = marker
        self.types = types

    async def fetch(self) -> Dict[str, Any]:
        """
        Выполняет GET-запрос к API для получения новых событий.

        Returns:
            Dict: Сырой JSON-ответ от API с новыми событиями.
        """
        bot = self._ensure_bot()

        params = bot.params.copy()

        if self.limit:
            params["limit"] = self.limit
        if self.marker is not None:
            params["marker"] = self.marker
        if self.timeout is not None:
            params["timeout"] = self.timeout
        if self.types:
            params["types"] = ",".join(self.types)

        event_json = await super().request(
            method=HTTPMethod.GET,
            path=ApiPath.UPDATES,
            model=None,
            params=params,
            is_return_raw=True,
        )

        return cast(Dict[str, Any], event_json)
