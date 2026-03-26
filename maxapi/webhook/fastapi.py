"""Интеграция с FastAPI для webhook-режима."""

from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from .base import DEFAULT_PATH, BaseMaxWebhook

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI

__all__ = ["FastAPIMaxWebhook"]


def _make_secret_dependency(secret: str):
    """Вернуть зависимость FastAPI для проверки секрета.

    Использует :func:`secrets.compare_digest` для защиты от
    timing-атак. При неверном или отсутствующем заголовке
    ``X-Max-Bot-Api-Secret`` поднимает ``HTTPException(403)``.
    """
    from secrets import compare_digest  # noqa: PLC0415

    from fastapi import Header, HTTPException  # noqa: PLC0415

    async def _check_secret(
        x_max_bot_api_secret: str | None = Header(default=None),
    ) -> None:
        if x_max_bot_api_secret is None or not compare_digest(
            x_max_bot_api_secret, secret
        ):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail="Forbidden",
            )

    return _check_secret


class FastAPIMaxWebhook(BaseMaxWebhook):
    """Интеграция диспетчера maxapi с FastAPI-приложением.

    Обеспечивает регистрацию POST-маршрута для приёма обновлений,
    парсинг JSON и инициализацию диспетчера через lifespan.

    Пример использования::

        from fastapi import FastAPI
        from maxapi import Dispatcher, Bot
        from maxapi.webhook.fastapi import FastAPIMaxWebhook

        dp = Dispatcher()
        bot = Bot(token="...")
        webhook = FastAPIMaxWebhook(dp=dp, bot=bot)

        # Вариант 1 — создать готовое приложение:
        app = webhook.create_app(path="/webhook")

        # Вариант 2 — подключить к существующему приложению:
        app = FastAPI(lifespan=webhook.lifespan)
        webhook.setup(app, path="/webhook")

        # uvicorn main:app --host 0.0.0.0 --port 8080
    """

    def __init__(
        self,
        dp,
        bot,
        *,
        secret: str | None = None,
    ) -> None:
        try:
            import fastapi  # noqa: F401, PLC0415
        except ImportError as exc:
            raise ImportError(
                "fastapi is not installed. "
                "Run: pip install fastapi  or  pip install maxapi[fastapi]"
            ) from exc

        super().__init__(dp, bot, secret=secret)

    @asynccontextmanager
    async def lifespan(self, app: "FastAPI") -> "AsyncGenerator[None, None]":
        """Инициализировать диспетчер в lifespan-контексте FastAPI.

        Передаётся напрямую в ``FastAPI(lifespan=webhook.lifespan)``.
        При компоновке с другими lifespan-менеджерами используйте
        ``contextlib.asynccontextmanager`` вручную.
        """
        await self._startup()
        yield

    def setup(self, app: "FastAPI", path: str = DEFAULT_PATH) -> None:
        """Зарегистрировать маршрут вебхука в FastAPI-приложении."""
        from fastapi import Depends, Request  # noqa: PLC0415
        from fastapi.responses import JSONResponse  # noqa: PLC0415

        dependencies = (
            [Depends(_make_secret_dependency(self.secret))]
            if self.secret is not None
            else []
        )

        @app.post(path, dependencies=dependencies)
        async def _webhook_route(request: Request) -> JSONResponse:
            """Обработать обновление от MAX."""
            event_json: dict[str, Any] = await request.json()
            await self._dispatch(event_json)
            return JSONResponse(
                content={"ok": True}, status_code=HTTPStatus.OK
            )

    def create_app(self, path: str = DEFAULT_PATH) -> "FastAPI":
        """Создать FastAPI-приложение с маршрутом и lifespan.

        Удобно для простых случаев, когда всё приложение — это
        только эндпоинт вебхука::

            app = webhook.create_app(path="/webhook")
            # uvicorn main:app --host 0.0.0.0 --port 8080
        """
        from fastapi import FastAPI  # noqa: PLC0415

        app = FastAPI(lifespan=self.lifespan)
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
        """Запустить FastAPI-приложение через uvicorn.

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
                "Run: pip install uvicorn  or  pip install maxapi[fastapi]"
            ) from exc

        app = self.create_app(path=path)
        config = Config(app=app, host=host, port=port, **kwargs)
        server = Server(config)
        await server.serve()
