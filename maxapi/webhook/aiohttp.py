"""Интеграция с aiohttp для webhook-режима."""

import asyncio
from http import HTTPStatus
from secrets import compare_digest
from typing import TYPE_CHECKING, Any

from ..loggers import logger_dp
from .base import DEFAULT_PATH, BaseMaxWebhook

if TYPE_CHECKING:
    from aiohttp import web

__all__ = ["AiohttpMaxWebhook"]


class AiohttpMaxWebhook(BaseMaxWebhook):
    """Интеграция диспетчера maxapi с aiohttp-приложением.

    Обеспечивает регистрацию POST-маршрута для приёма обновлений,
    парсинг JSON и инициализацию диспетчера в хуке запуска.

    При передаче ``secret`` фреймворк **автоматически** проверяет
    заголовок ``X-Max-Bot-Api-Secret`` в каждом входящем запросе
    (возвращает ``403 Forbidden`` при несоответствии).  Для полной
    защиты тот же ``secret`` нужно передать в
    :meth:`~maxapi.Bot.subscribe_webhook`, чтобы платформа MAX
    добавляла этот заголовок к каждому запросу.

    Пример использования::

        import aiohttp.web as web
        from maxapi import Dispatcher, Bot
        from maxapi.webhook.aiohttp import AiohttpMaxWebhook

        dp = Dispatcher()
        bot = Bot(token="...")
        webhook = AiohttpMaxWebhook(dp=dp, bot=bot, secret="my-secret")

        # Вариант 1 — создать готовое приложение:
        app = webhook.create_app(path="/webhook")
        web.run_app(app, host="0.0.0.0", port=8080)

        # Вариант 2 — подключить к существующему приложению:
        app = web.Application()
        app.on_startup.append(webhook.on_startup)
        webhook.setup(app, path="/webhook")
    """

    async def on_startup(self, app: "web.Application") -> None:
        """Инициализировать диспетчер при старте приложения.

        Добавьте в ``app.on_startup`` при подключении к
        существующему приложению::

            app.on_startup.append(webhook.on_startup)
        """
        await self._startup()

    def setup(self, app: "web.Application", path: str = DEFAULT_PATH) -> None:
        """Зарегистрировать маршрут вебхука в aiohttp-приложении."""
        from aiohttp import web  # noqa: PLC0415

        secret = self.secret

        async def _webhook_handler(
            request: web.Request,
        ) -> web.Response:
            """Принять обновление и передать диспетчеру."""
            if secret is not None:
                incoming = request.headers.get("X-Max-Bot-Api-Secret")
                if incoming is None or not compare_digest(incoming, secret):
                    return web.Response(
                        status=HTTPStatus.FORBIDDEN, text="Forbidden"
                    )

            event_json: dict[str, Any] = await request.json()
            await self._dispatch(event_json)
            return web.json_response({"ok": True}, status=HTTPStatus.OK)

        app.router.add_post(path, _webhook_handler)

    def create_app(self, path: str = DEFAULT_PATH) -> "web.Application":
        """Создать aiohttp-приложение с маршрутом и хуком запуска.

        Удобно для простых случаев, когда всё приложение — это
        только эндпоинт вебхука::

            app = webhook.create_app(path="/webhook")
            aiohttp.web.run_app(app, host="0.0.0.0", port=8080)
        """
        from aiohttp import web  # noqa: PLC0415

        app = web.Application()
        app.on_startup.append(self.on_startup)
        self.setup(app, path)
        return app

    async def run(
        self,
        *,
        host: str = "0.0.0.0",  # noqa: S104
        port: int = 8080,
        path: str = DEFAULT_PATH,
        **kwargs: Any,
    ) -> None:
        """Запустить aiohttp-сервер и ждать завершения.

        Создаёт приложение через :meth:`create_app`, поднимает
        ``AppRunner`` + ``TCPSite`` и блокируется до отмены задачи,
        после чего корректно завершает работу runner'а.

        Args:
            host: Хост сервера (по умолчанию ``"0.0.0.0"``).
            port: Порт сервера (по умолчанию ``8080``).
            path: URL-путь для маршрута вебхука.
            **kwargs: Дополнительные аргументы для ``AppRunner``.
        """
        from aiohttp import web  # noqa: PLC0415

        app = self.create_app(path=path)
        runner = web.AppRunner(app, **kwargs)
        await runner.setup()
        site = web.TCPSite(runner, host=host, port=port)
        await site.start()

        logger_dp.info(
            "Webhook сервер запущен на http://%s:%d%s", host, port, path
        )

        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()
