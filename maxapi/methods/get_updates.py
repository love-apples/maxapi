from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Optional, Sequence

from ..enums.update import UpdateType
from ..enums.http_method import HTTPMethod
from ..enums.api_path import ApiPath

from ..connection.base import BaseConnection


if TYPE_CHECKING:
    from ..bot import Bot


class GetUpdates(BaseConnection):
    """
    Класс для получения обновлений (updates) от API.

    Запрашивает новые события для бота через long polling
    с возможностью фильтрации по типам и маркеру последнего обновления.

    Args:
        bot (Bot): Экземпляр бота, через который выполняется запрос.

        limit (int, optional): Максимальное количество обновлений для получения.
            Диапазон: 1–1000. По умолчанию — 100.

        timeout (int, optional): Тайм-аут ожидания (long polling) в секундах.
            Диапазон: 0–90. По умолчанию — 30.

        marker (Optional[int], optional): Если указан, API вернёт события,
            которые идут после этого ID. Если None — вернутся все новые события.

        types (Optional[Sequence[UpdateType]], optional): Список типов событий,
            которые требуется получить (например: ``[UpdateType.MESSAGE_CREATED, UpdateType.MESSAGE_CALLBACK]``).
            Если None — вернутся все типы событий.

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
        limit: int = 100,
        timeout: int = 30,
        marker: Optional[int] = None,
        types: Optional[Sequence[UpdateType]] = None
    ):
        self.bot = bot
        self.limit = limit
        self.timeout = timeout
        self.marker = marker
        self.types = types

    async def fetch(self) -> Dict:
        """
        Выполняет GET-запрос к API для получения новых событий.

        Формирует параметры запроса в соответствии со спецификацией:
        - ``limit`` — максимальное количество обновлений (1–1000, по умолчанию 100);
        - ``timeout`` — тайм-аут ожидания (0–90 секунд, по умолчанию 30);
        - ``marker`` — ID последнего полученного события (если указан);
        - ``types`` — список типов событий (например: ``message_created,message_callback``).

        Returns:
            Dict: Сырой JSON-ответ от API с новыми событиями.

        Raises:
            RuntimeError: Если бот (`self.bot`) не был инициализирован.
            HTTPException: Если API вернул ошибку.
        """
        if self.bot is None:
            raise RuntimeError('Bot не инициализирован')

        params = self.bot.params.copy()
        params['limit'] = self.limit

        if self.marker is not None:
            params['marker'] = self.marker
        if self.timeout is not None:
            params['timeout'] = self.timeout
        if self.types:
            params['types'] = ','.join(self.types)

        event_json = await super().request(
            method=HTTPMethod.GET,
            path=ApiPath.UPDATES,
            model=None,
            params=params,
            is_return_raw=True
        )

        return event_json
