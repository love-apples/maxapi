from __future__ import annotations

import asyncio
import functools
from asyncio.exceptions import TimeoutError as AsyncioTimeoutError
from datetime import datetime
from re import DOTALL, search
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
)

from aiohttp import ClientConnectorError

from .context import BaseContext, MemoryContext
from .enums.update import UpdateType
from .exceptions.dispatcher import HandlerException, MiddlewareException
from .exceptions.max import InvalidToken, MaxApiError, MaxConnection
from .filters import filter_attrs
from .filters.command import CommandsInfo
from .filters.handler import Handler
from .loggers import logger_dp
from .methods.types.getted_updates import (
    process_update_request,
    process_update_webhook,
)
from .types.bot_mixin import BotMixin
from .utils.time import from_ms, to_ms

try:
    from fastapi.responses import JSONResponse  # type: ignore

    FASTAPI_INSTALLED = True
except ImportError:
    FASTAPI_INSTALLED = False


try:
    from uvicorn import Config, Server  # type: ignore

    UVICORN_INSTALLED = True
except ImportError:
    UVICORN_INSTALLED = False


if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import FastAPI, Request
    from magic_filter import MagicFilter

    from .bot import Bot
    from .filters.filter import BaseFilter
    from .filters.middleware import BaseMiddleware
    from .types.updates import UpdateUnion

CONNECTION_RETRY_DELAY = 30
GET_UPDATES_RETRY_DELAY = 5
COMMANDS_INFO_PATTERN = r"commands_info:\s*(.*?)(?=\n|$)"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8080


class Dispatcher(BotMixin):
    """
    Основной класс для обработки событий бота.

    Обеспечивает запуск поллинга и вебхука, маршрутизацию событий,
    применение middleware, фильтров и вызов соответствующих обработчиков.
    """

    def __init__(
        self,
        router_id: str | None = None,
        storage: Any = MemoryContext,
        *,
        use_create_task: bool = False,
        **storage_kwargs: Any,
    ) -> None:
        """
        Инициализация диспетчера.

        Args:
            router_id (str | None): Идентификатор роутера для логов.
            use_create_task (bool): Флаг, отвечающий за параллелизацию
                обработок событий.
            storage (type[BaseContext]): Класс контекста для хранения
                данных (MemoryContext, RedisContext и т.д.).
            **storage_kwargs (Any): Дополнительные аргументы для
                инициализации хранилища.
        """

        self.router_id = router_id
        self.storage = storage
        self.storage_kwargs = storage_kwargs

        self.event_handlers: list[Handler] = []
        self.contexts: dict[tuple[int | None, int | None], BaseContext] = {}
        self.routers: list[Router | Dispatcher] = []
        self.filters: list[MagicFilter] = []
        self.base_filters: list[BaseFilter] = []
        self.middlewares: list[BaseMiddleware] = []

        self.bot: Bot | None = None
        self.webhook_app: FastAPI | None = None
        self.on_started_func: Callable | None = None
        self.polling = False
        self.use_create_task = use_create_task

        self.message_created = Event(
            update_type=UpdateType.MESSAGE_CREATED, router=self
        )
        self.bot_added = Event(update_type=UpdateType.BOT_ADDED, router=self)
        self.bot_removed = Event(
            update_type=UpdateType.BOT_REMOVED, router=self
        )
        self.bot_started = Event(
            update_type=UpdateType.BOT_STARTED, router=self
        )
        self.bot_stopped = Event(
            update_type=UpdateType.BOT_STOPPED, router=self
        )
        self.dialog_cleared = Event(
            update_type=UpdateType.DIALOG_CLEARED, router=self
        )
        self.dialog_muted = Event(
            update_type=UpdateType.DIALOG_MUTED, router=self
        )
        self.dialog_unmuted = Event(
            update_type=UpdateType.DIALOG_UNMUTED, router=self
        )
        self.dialog_removed = Event(
            update_type=UpdateType.DIALOG_REMOVED, router=self
        )
        self.raw_api_response = Event(
            update_type=UpdateType.RAW_API_RESPONSE, router=self
        )
        self.chat_title_changed = Event(
            update_type=UpdateType.CHAT_TITLE_CHANGED, router=self
        )
        self.message_callback = Event(
            update_type=UpdateType.MESSAGE_CALLBACK, router=self
        )
        self.message_chat_created = Event(
            update_type=UpdateType.MESSAGE_CHAT_CREATED,
            router=self,
            deprecated=True,
        )
        self.message_edited = Event(
            update_type=UpdateType.MESSAGE_EDITED, router=self
        )
        self.message_removed = Event(
            update_type=UpdateType.MESSAGE_REMOVED, router=self
        )
        self.user_added = Event(update_type=UpdateType.USER_ADDED, router=self)
        self.user_removed = Event(
            update_type=UpdateType.USER_REMOVED, router=self
        )
        self.on_started = Event(update_type=UpdateType.ON_STARTED, router=self)

    def webhook_post(self, path: str) -> Callable[[Callable[..., Any]], Any]:
        def decorator(func: Callable[..., Any]) -> Any:
            if self.webhook_app is None:
                try:
                    from fastapi import FastAPI  # type: ignore
                except ImportError as exc:
                    raise ImportError(
                        "\n\t Не установлен fastapi!"
                        "\n\t Выполните команду для установки fastapi: "
                        "\n\t pip install fastapi"
                        "\n\t Или сразу все зависимости для работы вебхука:"
                        "\n\t pip install maxapi[webhook]"
                    ) from exc
                self.webhook_app = FastAPI()
            return self.webhook_app.post(path)(func)

        return decorator

    async def check_me(self) -> None:
        """
        Проверяет и логирует информацию о боте.
        """

        me = await self._ensure_bot().get_me()

        self._ensure_bot()._me = me

        logger_dp.info(
            f"Бот: @{me.username} first_name={me.first_name} id={me.user_id}"
        )

    def build_middleware_chain(
        self,
        middlewares: list[BaseMiddleware],
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
    ) -> Callable[[Any, dict[str, Any]], Awaitable[Any]]:
        """
        Формирует цепочку вызова middleware вокруг хендлера.

        Args:
            middlewares (List[BaseMiddleware]): Список middleware.
            handler (Callable): Финальный обработчик.

        Returns:
            Callable: Обёрнутый обработчик.
        """

        for mw in reversed(middlewares):
            handler = functools.partial(mw, handler)

        return handler

    def include_routers(self, *routers: Router) -> None:
        """
        Добавляет указанные роутеры в диспетчер.

        Args:
            *routers (Router): Роутеры для добавления.
        """

        self.routers.extend(routers)

    def outer_middleware(self, middleware: BaseMiddleware) -> None:
        """
        Добавляет Middleware на первое место в списке.

        Args:
            middleware (BaseMiddleware): Middleware.
        """

        self.middlewares.insert(0, middleware)

    def middleware(self, middleware: BaseMiddleware) -> None:
        """
        Добавляет Middleware в конец списка.

        Args:
            middleware (BaseMiddleware): Middleware.
        """

        self.middlewares.append(middleware)

    def filter(self, base_filter: BaseFilter) -> None:
        """
        Добавляет фильтр в список.

        Args:
            base_filter (BaseFilter): Фильтр.
        """

        self.base_filters.append(base_filter)

    async def __ready(self, bot: Bot) -> None:
        """
        Подготавливает диспетчер: сохраняет бота, регистрирует
        обработчики, вызывает on_started.

        Args:
            bot (Bot): Экземпляр бота.
        """

        self.bot = bot
        self.bot.dispatcher = self

        if self.polling and self.bot.auto_check_subscriptions:
            response = await self.bot.get_subscriptions()

            if response.subscriptions:
                logger_subscriptions_text = ", ".join(
                    [s.url for s in response.subscriptions]
                )
                logger_dp.warning(
                    "БОТ ИГНОРИРУЕТ POLLING! "
                    "Обнаружены установленные подписки: %s",
                    logger_subscriptions_text,
                )

        await self.check_me()

        self.routers += [self]

        for router in self.routers:
            router.bot = bot

            for handler in router.event_handlers:
                if handler.base_filters is None:
                    continue

                for base_filter in handler.base_filters:
                    commands = getattr(base_filter, "commands", None)

                    if commands and type(commands) is list:
                        handler_doc = handler.func_event.__doc__
                        extracted_info = None

                        if handler_doc:
                            from_pattern = search(
                                COMMANDS_INFO_PATTERN, handler_doc, DOTALL
                            )
                            if from_pattern:
                                extracted_info = from_pattern.group(1).strip()

                        self.bot.commands.append(
                            CommandsInfo(commands, extracted_info)
                        )

        handlers_count = sum(
            len(router.event_handlers) for router in self.routers
        )

        logger_dp.info(f"{handlers_count} событий на обработку")

        if self.on_started_func:
            await self.on_started_func()

    def __get_context(
        self, chat_id: int | None, user_id: int | None
    ) -> BaseContext:
        """
        Возвращает существующий или создаёт новый контекст
        по chat_id и user_id.

        Args:
            chat_id (Optional[int]): Идентификатор чата.
            user_id (Optional[int]): Идентификатор пользователя.

        Returns:
            BaseContext: Контекст.
        """

        key = (chat_id, user_id)
        if key in self.contexts:
            return self.contexts[key]

        new_ctx = self.storage(chat_id, user_id, **self.storage_kwargs)
        self.contexts[key] = new_ctx
        return new_ctx

    async def call_handler(
        self,
        handler: Handler,
        event_object: UpdateType | dict[str, Any],
        data: dict[str, Any],
    ) -> None:
        """
        Вызывает хендлер с нужными аргументами.

        Args:
            handler: Handler.
            event_object: Объект события.
            data: Данные для хендлера.

        Returns:
            None
        """

        func_args = handler.func_event.__annotations__.keys()
        kwargs_filtered = {k: v for k, v in data.items() if k in func_args}

        if kwargs_filtered:
            await handler.func_event(event_object, **kwargs_filtered)
        else:
            await handler.func_event(event_object)

    async def process_base_filters(
        self, event: UpdateUnion, filters: list[BaseFilter]
    ) -> dict[str, Any] | None | Literal[False]:
        """
        Асинхронно применяет фильтры к событию.

        Args:
            event (UpdateUnion): Событие.
            filters (List[BaseFilter]): Список фильтров.

        Returns:
            Optional[Dict[str, Any]] | Literal[False]: Словарь с
                результатом или False.
        """

        data = {}

        for _filter in filters:
            result = await _filter(event)

            if isinstance(result, dict):
                data.update(result)

            elif not result:
                return result

        return data

    async def _check_router_filters(
        self, event: UpdateUnion, router: Router | Dispatcher
    ) -> dict[str, Any] | None | Literal[False]:
        """
        Проверяет фильтры роутера для события.

        Args:
            event (UpdateUnion): Событие.
            router (Router | Dispatcher): Роутер для проверки.

        Returns:
            Optional[Dict[str, Any]] | Literal[False]: Словарь с данными
                или False, если фильтры не прошли.
        """
        if router.filters and not filter_attrs(event, *router.filters):
            return False

        if router.base_filters:
            result = await self.process_base_filters(
                event=event, filters=router.base_filters
            )
            if isinstance(result, dict):
                return result
            if not result:
                return False

        return {}

    def _find_matching_handlers(
        self, router: Router | Dispatcher, event_type: UpdateType
    ) -> list[Handler]:
        """
        Находит обработчики, соответствующие типу события в роутере.

        Args:
            router (Router | Dispatcher): Роутер для поиска.
            event_type (UpdateType): Тип события.

        Returns:
            List[Handler]: Список подходящих обработчиков.
        """
        return [
            handler
            for handler in router.event_handlers
            if handler.update_type == event_type
        ]

    async def _check_handler_match(
        self,
        handler: Handler,
        event: UpdateUnion,
        current_state: Any | None,
    ) -> dict[str, Any] | None | Literal[False]:
        """
        Проверяет, подходит ли обработчик для события (фильтры, состояние).

        Args:
            handler (Handler): Обработчик для проверки.
            event (UpdateUnion): Событие.
            current_state (Optional[Any]): Текущее состояние.

        Returns:
            Optional[Dict[str, Any]] | Literal[False]: Словарь с данными
                или False, если не подходит.
        """
        if handler.filters and not filter_attrs(event, *handler.filters):
            return False

        if handler.states and current_state not in handler.states:
            return False

        if handler.base_filters:
            result = await self.process_base_filters(
                event=event, filters=handler.base_filters
            )
            if isinstance(result, dict):
                return result
            if not result:
                return False

        return {}

    async def _execute_handler(
        self,
        handler: Handler,
        event: UpdateUnion,
        data: dict[str, Any],
        handler_middlewares: list[BaseMiddleware],
        memory_context: BaseContext,
        current_state: Any | None,
        router_id: Any,
        process_info: str,
    ) -> None:
        """
        Выполняет обработчик с построением цепочки middleware
        и обработкой ошибок.

        Args:
            handler (Handler): Обработчик для выполнения.
            event (UpdateUnion): Событие.
            data (Dict[str, Any]): Данные для обработчика.
            handler_middlewares (List[BaseMiddleware]): Middleware для
                обработчика.
            memory_context (BaseContext): Контекст памяти.
            current_state (Optional[Any]): Текущее состояние.
            router_id (Any): Идентификатор роутера для логов.
            process_info (str): Информация о процессе для логов.

        Raises:
            HandlerException: При ошибке выполнения обработчика.
        """
        func_args = handler.func_event.__annotations__.keys()
        kwargs_filtered = {k: v for k, v in data.items() if k in func_args}

        if "context" not in kwargs_filtered and "context" in data:
            kwargs_filtered["context"] = data["context"]

        handler_chain = self.build_middleware_chain(
            handler_middlewares,
            functools.partial(self.call_handler, handler),
        )

        try:
            await handler_chain(event, kwargs_filtered)
        except Exception as e:
            mem_data = await memory_context.get_data()
            raise HandlerException(
                handler_title=handler.func_event.__name__,
                router_id=router_id,
                process_info=process_info,
                memory_context={
                    "data": mem_data,
                    "state": current_state,
                },
                cause=e,
            ) from e

    async def handle_raw_response(
        self, event_type: UpdateType, raw_data: dict[str, Any]
    ) -> None:
        """
        Специальный метод для обработки сырых ответов API.
        """
        for router in self.routers:
            matching_handlers = self._find_matching_handlers(
                router, event_type
            )
            for handler in matching_handlers:
                try:
                    await self.call_handler(handler, raw_data, {})
                except Exception as e:  # noqa: PERF203
                    logger_dp.exception(
                        f"Ошибка в обработчике RAW_API_RESPONSE: {e}"
                    )

    async def handle(self, event_object: UpdateUnion) -> None:
        """
        Основной обработчик события. Применяет фильтры, middleware
        и вызывает нужный handler.

        Args:
            event_object (UpdateUnion): Событие.
        """

        router_id = None
        process_info = "нет данных"

        try:
            ids = event_object.get_ids()
            memory_context = self.__get_context(*ids)
            current_state = await memory_context.get_state()
            kwargs = {"context": memory_context}

            process_info = (
                f"{event_object.update_type} | "
                f"chat_id: {ids[0]}, user_id: {ids[1]}"
            )

            is_handled = False

            async def _process_event(
                _: UpdateUnion, data: dict[str, Any]
            ) -> None:
                nonlocal router_id, is_handled, memory_context, current_state

                data["context"] = memory_context

                for index, router in enumerate(self.routers):
                    if is_handled:
                        break

                    router_id = router.router_id or index

                    router_filter_result = await self._check_router_filters(
                        event_object, router
                    )

                    if router_filter_result is False:
                        continue

                    if isinstance(router_filter_result, dict):
                        data.update(router_filter_result)

                    matching_handlers = self._find_matching_handlers(
                        router, event_object.update_type
                    )

                    async def _process_handlers(
                        event: UpdateUnion, handler_data: dict[str, Any]
                    ) -> None:
                        nonlocal is_handled

                        for handler in matching_handlers:
                            handler_match_result = (
                                await self._check_handler_match(
                                    handler, event, current_state
                                )
                            )

                            if handler_match_result is False:
                                continue

                            if isinstance(handler_match_result, dict):
                                handler_data.update(handler_match_result)

                            await self._execute_handler(
                                handler=handler,
                                event=event,
                                data=handler_data,
                                handler_middlewares=handler.middlewares,
                                memory_context=memory_context,
                                current_state=current_state,
                                router_id=router_id,
                                process_info=process_info,
                            )

                            logger_dp.info(
                                f"Обработано: "
                                f"router_id: {router_id} | {process_info}"
                            )

                            is_handled = True
                            break

                    if isinstance(router, Router) and router.middlewares:
                        router_chain = self.build_middleware_chain(
                            router.middlewares, _process_handlers
                        )
                        await router_chain(event_object, data)
                    else:
                        await _process_handlers(event_object, data)

            global_chain = self.build_middleware_chain(
                self.middlewares, _process_event
            )

            try:
                await global_chain(event_object, kwargs)
            except Exception as e:
                mem_data = await memory_context.get_data()

                if hasattr(global_chain, "func"):
                    middleware_title = global_chain.func.__class__.__name__  # type: ignore[attr-defined]
                else:
                    middleware_title = getattr(
                        global_chain,
                        "__name__",
                        global_chain.__class__.__name__,
                    )

                raise MiddlewareException(
                    middleware_title=middleware_title,
                    router_id=router_id,
                    process_info=process_info,
                    memory_context={
                        "data": mem_data,
                        "state": current_state,
                    },
                    cause=e,
                ) from e

            if not is_handled:
                logger_dp.info(
                    f"Проигнорировано: router_id: {router_id} | {process_info}"
                )

        except Exception as e:
            logger_dp.exception(
                f"Ошибка при обработке события: router_id: "
                f"{router_id} | {process_info} | {e} "
            )

    async def start_polling(
        self, bot: Bot, *, skip_updates: bool = False
    ) -> None:
        """
        Запускает цикл получения обновлений (long polling).

        Args:
            bot (Bot): Экземпляр бота.
            skip_updates (bool): Флаг, отвечающий за обработку старых событий.
        """

        self.polling = True

        await self.__ready(bot)

        current_timestamp = to_ms(datetime.now())

        while self.polling:
            try:
                events: dict = await self._ensure_bot().get_updates(
                    marker=self._ensure_bot().marker_updates
                )
            except AsyncioTimeoutError:
                continue
            except (MaxConnection, ClientConnectorError) as e:
                logger_dp.warning(
                    f"Ошибка подключения при получении обновлений: {e}, "
                    f"жду {CONNECTION_RETRY_DELAY} секунд"
                )
                await asyncio.sleep(CONNECTION_RETRY_DELAY)
                continue
            except InvalidToken:
                logger_dp.error("Неверный токен! Останавливаю polling")
                self.polling = False
                raise
            except MaxApiError as e:
                logger_dp.info(
                    f"Ошибка при получении обновлений: {e}, "
                    f"жду {GET_UPDATES_RETRY_DELAY} секунд"
                )
                await asyncio.sleep(GET_UPDATES_RETRY_DELAY)
                continue
            except Exception as e:
                logger_dp.error(
                    f"Неожиданная ошибка при получении обновлений: "
                    f"{e.__class__.__name__}: {e}"
                )
                await asyncio.sleep(GET_UPDATES_RETRY_DELAY)
                continue

            try:
                self._ensure_bot().marker_updates = events.get("marker")

                processed_events = await process_update_request(
                    events=events, bot=self._ensure_bot()
                )

                for event in processed_events:
                    if skip_updates and event.timestamp < current_timestamp:
                        logger_dp.info(
                            f"Пропуск события от {from_ms(event.timestamp)}: "
                            f"{event.update_type}"
                        )
                        continue

                    if self.use_create_task:
                        asyncio.create_task(self.handle(event))

                    else:
                        await self.handle(event)

            except ClientConnectorError:
                logger_dp.error(
                    f"Ошибка подключения, жду {CONNECTION_RETRY_DELAY} секунд"
                )
                await asyncio.sleep(CONNECTION_RETRY_DELAY)
            except Exception as e:
                logger_dp.error(
                    f"Общая ошибка при обработке событий: {e.__class__} - {e}"
                )

    async def stop_polling(self) -> None:
        """
        Останавливает цикл получения обновлений (long polling).

        Этот метод устанавливает флаг polling в False, что приводит к
        завершению цикла в методе start_polling.
        """
        if self.polling:
            self.polling = False
            logger_dp.info("Polling остановлен")

    async def handle_webhook(
        self,
        bot: Bot,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        **kwargs: Any,
    ) -> None:
        """
        Запускает FastAPI-приложение для приёма обновлений через вебхук.

        Args:
            bot (Bot): Экземпляр бота.
            host (str): Хост сервера.
            port (int): Порт сервера.
        """

        if not FASTAPI_INSTALLED:
            raise ImportError(
                "\n\t Не установлен fastapi!"
                "\n\t Выполните команду для установки fastapi: "
                "\n\t pip install fastapi>=0.68.0"
                "\n\t Или сразу все зависимости для работы вебхука:"
                "\n\t pip install maxapi[webhook]"
            )

        elif not UVICORN_INSTALLED:
            raise ImportError(
                "\n\t Не установлен uvicorn!"
                "\n\t Выполните команду для установки uvicorn: "
                "\n\t pip install uvicorn>=0.15.0"
                "\n\t Или сразу все зависимости для работы вебхука:"
                "\n\t pip install maxapi[webhook]"
            )

        @self.webhook_post("/")
        async def _(request: Request) -> JSONResponse:
            event_json = await request.json()
            event_object = await process_update_webhook(
                event_json=event_json, bot=bot
            )

            if self.use_create_task:
                asyncio.create_task(self.handle(event_object))
            else:
                await self.handle(event_object)

            return JSONResponse(  # pyright: ignore[reportPossiblyUnboundVariable]
                content={"ok": True}, status_code=200
            )

        await self.init_serve(bot=bot, host=host, port=port, **kwargs)

    async def init_serve(
        self,
        bot: Bot,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        **kwargs: Any,
    ) -> None:
        """
        Запускает сервер для обработки вебхуков.

        Args:
            bot (Bot): Экземпляр бота.
            host (str): Хост.
            port (int): Порт.
        """

        if not UVICORN_INSTALLED:
            raise ImportError(
                "\n\t Не установлен uvicorn!"
                "\n\t Выполните команду для установки uvicorn: "
                "\n\t pip install uvicorn>=0.15.0"
                "\n\t Или сразу все зависимости для работы вебхука:"
                "\n\t pip install maxapi[webhook]"
            )

        if self.webhook_app is None:
            raise RuntimeError("webhook_app не инициализирован")

        config = Config(  # pyright: ignore[reportPossiblyUnboundVariable]
            app=self.webhook_app, host=host, port=port, **kwargs
        )
        server = Server(  # pyright: ignore[reportPossiblyUnboundVariable]
            config
        )

        await self.__ready(bot)

        await server.serve()


class Router(Dispatcher):
    """
    Роутер для группировки обработчиков событий.
    """

    def __init__(self, router_id: str | None = None):
        """
        Инициализация роутера.

        Args:
            router_id (str | None): Идентификатор роутера для логов.
        """

        super().__init__(router_id)


class Event:
    """
    Декоратор для регистрации обработчиков событий.
    """

    def __init__(
        self,
        update_type: UpdateType,
        router: Dispatcher | Router,
        *,
        deprecated: bool = False,
    ):
        """
        Инициализирует событие-декоратор.

        Args:
            update_type (UpdateType): Тип события.
            router (Dispatcher | Router): Экземпляр роутера или диспетчера.
            deprecated (bool): Флаг, указывающий на то, что событие устарело.
        """

        self.update_type = update_type
        self.router = router
        self.deprecated = deprecated

    def register(
        self, func_event: Callable, *args: Any, **kwargs: Any
    ) -> Callable:
        """
        Регистрирует функцию как обработчик события.

        Args:
            func_event (Callable): Функция-обработчик
            *args: Фильтры
            **kwargs: Дополнительные параметры (например, states)

        Returns:
            Callable: Исходная функция.
        """

        if self.deprecated:
            import warnings

            warnings.warn(
                f"Событие {self.update_type} устарело "
                f"и будет удалено в будущих версиях.",
                DeprecationWarning,
                stacklevel=3,
            )

        if self.update_type == UpdateType.ON_STARTED:
            self.router.on_started_func = func_event

        else:
            self.router.event_handlers.append(
                Handler(
                    *args,
                    func_event=func_event,
                    update_type=self.update_type,
                    **kwargs,
                )
            )
        return func_event

    def __call__(self, *args: Any, **kwargs: Any) -> Callable:
        """
        Регистрирует функцию как обработчик события через декоратор.

        Returns:
            Callable: Декоратор.
        """

        def decorator(func_event: Callable) -> Callable:
            return self.register(func_event, *args, **kwargs)

        return decorator
