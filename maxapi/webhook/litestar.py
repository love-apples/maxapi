"""Интеграция с Litestar для webhook-режима."""

from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from .base import DEFAULT_PATH, BaseMaxWebhook

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.handlers import HTTPRouteHandler

__all__ = ["LitestarMaxWebhook"]


def _make_secret_guard(secret: str):
    """Вернуть guard Litestar для проверки секрета.

    Использует :func:`secrets.compare_digest` для защиты от
    timing-атак. При неверном или отсутствующем заголовке
    ``X-Max-Bot-Api-Secret`` поднимает
    ``PermissionDeniedException`` (HTTP 403).
    """
    from secrets import compare_digest  # noqa: PLC0415

    from litestar.connection import ASGIConnection  # noqa: PLC0415
    from litestar.exceptions import (  # noqa: PLC0415
        PermissionDeniedException,
    )
    from litestar.handlers import BaseRouteHandler  # noqa: PLC0415

    async def _check_secret(
        connection: ASGIConnection, _: BaseRouteHandler
    ) -> None:
        incoming = connection.headers.get("X-Max-Bot-Api-Secret")
        if incoming is None or not compare_digest(incoming, secret):
            raise PermissionDeniedException("Forbidden")

    return _check_secret


class LitestarMaxWebhook(BaseMaxWebhook):
    """Интеграция диспетчера maxapi с Litestar-приложением.

    Обеспечивает создание POST-обработчика маршрута для приёма
    обновлений, парсинг JSON и инициализацию диспетчера в хуке
    запуска.

    Пример использования::

        from litestar import Litestar
        from maxapi import Dispatcher, Bot
        from maxapi.webhook.litestar import LitestarMaxWebhook

        dp = Dispatcher()
        bot = Bot(token="...")
        webhook = LitestarMaxWebhook(dp=dp, bot=bot)

        # Вариант 1 — создать готовое приложение:
        app = webhook.create_app(path="/webhook")

        # Вариант 2 — подключить к существующему приложению:
        handler = webhook.make_handler(path="/webhook")
        app = Litestar(
            route_handlers=[handler],
            on_startup=[webhook.on_startup],
        )
    """

    async def on_startup(self) -> None:
        """Инициализировать диспетчер при старте приложения.

        Передаётся в ``on_startup`` при ручной сборке приложения::

            app = Litestar(
                route_handlers=[...],
                on_startup=[webhook.on_startup],
            )
        """
        await self._startup()

    def make_handler(self, path: str = DEFAULT_PATH) -> "HTTPRouteHandler":
        """Вернуть настроенный POST-обработчик маршрута Litestar.

        Используйте при подключении к существующему приложению::

            handler = webhook.make_handler(path="/webhook")
            app = Litestar(
                route_handlers=[handler],
                on_startup=[webhook.on_startup],
            )
        """
        from litestar import Request, post  # noqa: PLC0415

        guards = (
            [_make_secret_guard(self.secret)]
            if self.secret is not None
            else None
        )

        dispatch = self._dispatch

        @post(path, status_code=HTTPStatus.OK, guards=guards)
        async def _webhook_handler(request: Request) -> dict[str, Any]:
            """Принять обновление и передать диспетчеру."""
            event_json: dict[str, Any] = await request.json()
            await dispatch(event_json)
            return {"ok": True}

        return _webhook_handler

    def create_app(self, path: str = DEFAULT_PATH) -> "Litestar":
        """Создать Litestar-приложение с маршрутом и хуком запуска.

        Удобно для простых случаев, когда всё приложение — это
        только эндпоинт вебхука::

            app = webhook.create_app(path="/webhook")
            # uvicorn main:app --host 0.0.0.0 --port 8080
        """
        from litestar import Litestar  # noqa: PLC0415

        return Litestar(
            route_handlers=[self.make_handler(path)],
            on_startup=[self.on_startup],
        )

    async def run(
        self,
        *,
        host: str = "0.0.0.0",  # noqa: S104
        port: int = 8080,
        path: str = DEFAULT_PATH,
        **kwargs: Any,
    ) -> None:
        """Запустить Litestar-приложение через uvicorn.

        Args:
            host: Хост сервера (по умолчанию ``"0.0.0.0"``).
            port: Порт сервера (по умолчанию ``8080``).
            path: URL-путь для маршрута вебхука.
            **kwargs: Дополнительные аргументы для ``uvicorn.Config``.
        """
        try:
            from uvicorn import (  # type: ignore[import]  # noqa: PLC0415
                Config,
                Server,
            )
        except ImportError as exc:
            raise ImportError(
                "uvicorn is not installed. "
                "Run: pip install uvicorn  or  pip install maxapi[litestar]"
            ) from exc

        app = self.create_app(path=path)
        config = Config(app=app, host=host, port=port, **kwargs)
        server = Server(config)
        await server.serve()
