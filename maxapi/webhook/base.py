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
from ..methods.types.getted_updates import (
    process_update_webhook,
    warn_unprocessable_event,
)

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
        self._background_tasks: set[asyncio.Task[Any]] = set()
        if not self.secret:
            logger_dp.warning(
                "Webhook запущен без secret. Передайте secret= в "
                "handle_webhook() или в конструктор вебхука. Тот же "
                "secret укажите в bot.subscribe_webhook(secret='...'). "
                "Фреймворк автоматически проверит X-Max-Bot-Api-Secret "
                "в каждом запросе."
            )

    async def _startup(self) -> None:
        """Инициализировать диспетчер."""
        await self.dp.startup(self.bot)

    async def _dispatch(self, event_json: dict[str, Any]) -> bool:
        """Распарсить и диспетчеризовать входящее обновление.

        Преобразует сырой JSON-payload в типизированный объект
        события и передаёт диспетчеру. Если событие не удалось
        разобрать (неизвестный тип или некорректное содержимое),
        логирует предупреждение.

        Returns:
            ``True``, если событие передано диспетчеру,
            ``False`` — если событие не удалось разобрать.
        """
        event_object = await process_update_webhook(
            event_json=event_json, bot=self.bot
        )

        if event_object is None:
            warn_unprocessable_event(event_json)
            return False

        if self.dp.use_create_task:
            task = asyncio.create_task(self.dp.handle(event_object))
            self._background_tasks.add(task)
            task.add_done_callback(self._on_background_task_done)
        else:
            await self.dp.handle(event_object)

        return True

    def _on_background_task_done(self, task: "asyncio.Task[Any]") -> None:
        """Callback завершения фоновой задачи (``use_create_task=True``).

        Удаляет задачу из пула и логирует необработанное исключение, если оно
        есть. Без явного вызова ``task.exception()`` Python при сборке мусора
        выдаст предупреждение *"Task exception was never retrieved"*.
        """
        self._background_tasks.discard(task)
        if not task.cancelled():
            exc = task.exception()
            if exc is not None:
                logger_dp.error(
                    "Необработанное исключение в фоновой задаче handle(): %r",
                    exc,
                    exc_info=exc,
                )

    async def _shutdown(self) -> None:
        """Дождаться фоновых задач обработки (``use_create_task=True``).

        Вызывается интеграциями при остановке приложения: без этого задачи,
        запущенные из ``_dispatch``, обрываются вместе с event loop.
        """
        if not self._background_tasks:
            return

        logger_dp.info(
            "Ожидаю завершения %d фоновых задач вебхука...",
            len(self._background_tasks),
        )
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        logger_dp.info("Все фоновые задачи вебхука завершены")

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
