"""Абстрактный базовый класс для webhook-интеграций."""

__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PATH",
    "DEFAULT_PORT",
    "BaseMaxWebhook",
]

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from ..loggers import logger_dp
from ..methods.types.getted_updates import process_update_webhook
from ..types.updates import UNKNOWN_UPDATE_DISCLAIMER

if TYPE_CHECKING:
    from ..bot import Bot
    from ..dispatcher import Dispatcher

DEFAULT_HOST = "0.0.0.0"  # noqa: S104
DEFAULT_PORT = 8080
DEFAULT_PATH = "/"


class BaseMaxWebhook(ABC):
    """Абстрактный базовый класс для интеграций вебхука.

    Содержит общую логику инициализации, запуска и
    диспетчеризации обновлений. Конкретные подклассы реализуют
    специфичную для фреймворка маршрутизацию и хуки жизненного
    цикла.

    Опциональный ``secret`` используется для проверки заголовка
    ``X-Max-Bot-Api-Secret`` и должен совпадать со значением,
    переданным в :meth:`~maxapi.Bot.subscribe_webhook`.
    """

    def __init__(
        self,
        dp: "Dispatcher",
        bot: "Bot",
        *,
        secret: str | None = None,
    ) -> None:
        self.dp = dp
        self.bot = bot
        self.secret = secret

    async def _startup(self) -> None:
        """Инициализировать диспетчер."""
        await self.dp.startup(self.bot)

    async def _dispatch(self, event_json: dict[str, Any]) -> bool:
        """Распарсить и диспетчеризовать входящее обновление.

        Преобразует сырой JSON-payload в типизированный объект
        события и передаёт диспетчеру. При нераспознанном типе
        обновления логирует предупреждение и возвращает ``False``.
        """
        event_object = await process_update_webhook(
            event_json=event_json, bot=self.bot
        )

        if event_object is None:
            msg = UNKNOWN_UPDATE_DISCLAIMER.format(
                update_type=event_json.get("update_type")
            )
            logger_dp.warning(msg)
            return False

        if self.dp.use_create_task:
            asyncio.create_task(self.dp.handle(event_object))
        else:
            await self.dp.handle(event_object)

        return True

    @abstractmethod
    def create_app(self, path: str = DEFAULT_PATH):
        """Создать и вернуть готовое к запуску веб-приложение."""

    @abstractmethod
    async def run(
        self,
        *,
        host: str = "0.0.0.0",  # noqa: S104
        port: int = 8080,
        path: str = DEFAULT_PATH,
        **kwargs: Any,
    ) -> None:
        """Запустить вебхук-сервер и ждать завершения.

        Args:
            host: Хост сервера.
            port: Порт сервера.
            path: URL-путь для маршрута вебхука.
            **kwargs: Дополнительные аргументы для конкретного runner'а.
        """
