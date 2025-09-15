from __future__ import annotations

import asyncio

import functools
from typing import Any, Awaitable, Callable, Dict, List, TYPE_CHECKING, Literal, Optional
from asyncio.exceptions import TimeoutError as AsyncioTimeoutError

from aiohttp import ClientConnectorError

from .exceptions.dispatcher import HandlerException, MiddlewareException

from .filters.filter import BaseFilter
from .filters.middleware import BaseMiddleware
from .filters.handler import Handler

from .context import MemoryContext
from .types.updates import UpdateUnion
from .types.errors import Error

from .methods.types.getted_updates import process_update_request, process_update_webhook

from .filters import filter_attrs

from .bot import Bot
from .enums.update import UpdateType
from .loggers import logger_dp


try:
    from fastapi import FastAPI, Request # type: ignore
    from fastapi.responses import JSONResponse # type: ignore
    FASTAPI_INSTALLED = True
except ImportError:
    FASTAPI_INSTALLED = False
    
    
try:
    from uvicorn import Config, Server # type: ignore
    UVICORN_INSTALLED = True
except ImportError:
    UVICORN_INSTALLED = False
    

if TYPE_CHECKING:
    from magic_filter import MagicFilter

CONNECTION_RETRY_DELAY = 30
GET_UPDATES_RETRY_DELAY = 5


class Dispatcher:
    
    """
    Основной класс для обработки событий бота.

    Обеспечивает запуск поллинга и вебхука, маршрутизацию событий,
    применение middleware, фильтров и вызов соответствующих обработчиков.
    """
    
    def __init__(self, router_id: str | None = None, use_create_task: bool = False) -> None:
        
        """
        Инициализация диспетчера.

        Args:
            router_id (str | None): Идентификатор роутера для логов.
            use_create_task (bool): Флаг отвечающий за параллелизацию обработок событий.
        """
        
        self.router_id = router_id
        
        self.event_handlers: List[Handler] = []
        self.contexts: List[MemoryContext] = []
        self.routers: List[Router | Dispatcher] = []
        self.filters: List[MagicFilter] = []
        self.base_filters: List[BaseFilter] = []
        self.middlewares: List[BaseMiddleware] = []
        
        self.bot: Optional[Bot] = None
        self.webhook_app: Optional[FastAPI] = None
        self.on_started_func: Optional[Callable] = None
        self.polling = False
        self.use_create_task = use_create_task

        self.message_created = Event(update_type=UpdateType.MESSAGE_CREATED, router=self)
        self.bot_added = Event(update_type=UpdateType.BOT_ADDED, router=self)
        self.bot_removed = Event(update_type=UpdateType.BOT_REMOVED, router=self)
        self.bot_started = Event(update_type=UpdateType.BOT_STARTED, router=self)
        self.bot_stopped = Event(update_type=UpdateType.BOT_STOPPED, router=self)
        self.dialog_cleared = Event(update_type=UpdateType.DIALOG_CLEARED, router=self)
        self.dialog_muted = Event(update_type=UpdateType.DIALOG_MUTED, router=self)
        self.dialog_unmuted = Event(update_type=UpdateType.DIALOG_UNMUTED, router=self)
        self.dialog_removed = Event(update_type=UpdateType.DIALOG_REMOVED, router=self)
        self.chat_title_changed = Event(update_type=UpdateType.CHAT_TITLE_CHANGED, router=self)
        self.message_callback = Event(update_type=UpdateType.MESSAGE_CALLBACK, router=self)
        self.message_chat_created = Event(update_type=UpdateType.MESSAGE_CHAT_CREATED, router=self)
        self.message_edited = Event(update_type=UpdateType.MESSAGE_EDITED, router=self)
        self.message_removed = Event(update_type=UpdateType.MESSAGE_REMOVED, router=self)
        self.user_added = Event(update_type=UpdateType.USER_ADDED, router=self)
        self.user_removed = Event(update_type=UpdateType.USER_REMOVED, router=self)
        self.on_started = Event(update_type=UpdateType.ON_STARTED, router=self)
        
    def webhook_post(self, path: str):
        def decorator(func):
            if self.webhook_app is None:
                try:
                    from fastapi import FastAPI # type: ignore
                except ImportError:
                    raise ImportError(
                        '\n\t Не установлен fastapi!'
                        '\n\t Выполните команду для установки fastapi: '
                        '\n\t pip install fastapi>=0.68.0'
                        '\n\t Или сразу все зависимости для работы вебхука:'
                        '\n\t pip install maxapi[webhook]'
                    )
                self.webhook_app = FastAPI()
            return self.webhook_app.post(path)(func)
        return decorator
        
    async def check_me(self):
        
        """
        Проверяет и логирует информацию о боте.
        """
        
        me = await self.bot.get_me()
        
        self.bot._me = me
        
        logger_dp.info(f'Бот: @{me.username} first_name={me.first_name} id={me.user_id}')
        
    def build_middleware_chain(
        self,
        middlewares: List[BaseMiddleware],
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]]
    ) -> Callable[[Any, Dict[str, Any]], Awaitable[Any]]:
        
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

    def include_routers(self, *routers: 'Router'):
        
        """
        Добавляет указанные роутеры в диспетчер.

        Args:
            *routers (Router): Роутеры для добавления.
        """
        
        self.routers += [r for r in routers]
        
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
            
    async def __ready(self, bot: Bot):
        
        """
        Подготавливает диспетчер: сохраняет бота, регистрирует обработчики, вызывает on_started.

        Args:
            bot (Bot): Экземпляр бота.
        """
        
        self.bot = bot
        
        if self.polling and self.bot.auto_check_subscriptions:
            response = await self.bot.get_subscriptions()
            
            if response.subscriptions:
                logger_subscriptions_text = ', '.join([s.url for s in response.subscriptions])
                logger_dp.warning('БОТ ИГНОРИРУЕТ POLLING! Обнаружены установленные подписки: %s', logger_subscriptions_text)
        
        await self.check_me()
        
        self.routers += [self]
        
        for router in self.routers:
            router.bot = bot
            
            for handler in router.event_handlers:
                for base_filter in handler.base_filters:
                    
                    commands = getattr(base_filter, 'commands', None)
                    
                    if commands:
                        if type(commands) is list:
                            self.bot.commands += commands
        
        handlers_count = sum(len(router.event_handlers) for router in self.routers)

        logger_dp.info(f'{handlers_count} событий на обработку')

        if self.on_started_func:
            await self.on_started_func()
            
    def __get_memory_context(self, chat_id: int, user_id: int):
        
        """
        Возвращает существующий или создаёт новый MemoryContext по chat_id и user_id.

        Args:
            chat_id (int): Идентификатор чата.
            user_id (int): Идентификатор пользователя.

        Returns:
            MemoryContext: Контекст.
        """

        for ctx in self.contexts:
            if ctx.chat_id == chat_id and ctx.user_id == user_id:
                return ctx
            
        new_ctx = MemoryContext(chat_id, user_id)
        self.contexts.append(new_ctx)
        return new_ctx
    
    async def call_handler(
        self, 
        handler: Handler, 
        event_object: UpdateType, 
        data: Dict[str, Any]
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
            self, 
            event: UpdateUnion, 
            filters: List[BaseFilter]
        ) -> Optional[Dict[str, Any]] | Literal[False]:
        
        """
        Асинхронно применяет фильтры к событию.

        Args:
            event (UpdateUnion): Событие.
            filters (List[BaseFilter]): Список фильтров.

        Returns:
            Optional[Dict[str, Any]] | Literal[False]: Словарь с результатом или False.
        """
        
        data = {}
        
        for _filter in filters:
            result = await _filter(event)
            
            if isinstance(result, dict):
                data.update(result)
                
            elif not result:
                return result
            
        return data

    async def handle(self, event_object: UpdateUnion):
        
        """
        Основной обработчик события. Применяет фильтры, middleware и вызывает нужный handler.

        Args:
            event_object (UpdateUnion): Событие.
        """
        
        router_id = None
        process_info = 'нет данных'
        
        try:
            ids = event_object.get_ids()
            memory_context = self.__get_memory_context(*ids)
            current_state = await memory_context.get_state()
            kwargs = {'context': memory_context}
            router_id = None
            
            process_info = f'{event_object.update_type} | chat_id: {ids[0]}, user_id: {ids[1]}'
            
            is_handled = False

            async def _process_event(_: UpdateUnion, data: Dict[str, Any]) -> None:
                
                nonlocal router_id, is_handled
                
                for index, router in enumerate(self.routers):
                    
                    if is_handled:
                        break
                    
                    router_id = router.router_id or index
                    
                    if router.filters:
                        if not filter_attrs(event_object, *router.filters):
                            continue
                        
                    result_router_filter = await self.process_base_filters(
                        event=event_object,
                        filters=router.base_filters
                    )
                    
                    if isinstance(result_router_filter, dict):
                        data.update(result_router_filter)
                        
                    elif not result_router_filter:
                        continue
                        
                    for handler in router.event_handlers:

                        if not handler.update_type == event_object.update_type:
                            continue

                        if handler.filters:
                            if not filter_attrs(event_object, *handler.filters):
                                continue
                        
                        if handler.states:
                            if current_state not in handler.states:
                                continue
                            
                        func_args = handler.func_event.__annotations__.keys()
                            
                        if handler.base_filters:
                            result_filter = await self.process_base_filters(
                                event=event_object,
                                filters=handler.base_filters
                            )
                            
                            if isinstance(result_filter, dict):
                                data.update(result_filter)
                                
                            elif not result_filter:
                                continue
                        
                        if isinstance(router, Router):
                            local_middlewares = router.middlewares + handler.middlewares
                        elif isinstance(router, Dispatcher):
                            local_middlewares = handler.middlewares
                        
                        handler_chain = self.build_middleware_chain(
                            local_middlewares,
                            functools.partial(self.call_handler, handler)
                        )
                        
                        kwargs_filtered = {k: v for k, v in data.items() if k in func_args}
                        
                        try:
                            await handler_chain(event_object, kwargs_filtered)
                        except Exception as e:
                            mem_data = await memory_context.get_data()
                            raise HandlerException(
                                handler_title=handler.func_event.__name__,
                                router_id=router_id,
                                process_info=process_info,
                                memory_context={
                                    'data': mem_data,
                                    'state': current_state,
                                },
                                cause=e,
                            ) from e

                        logger_dp.info(f'Обработано: router_id: {router_id} | {process_info}')

                        is_handled = True
                        break

            global_chain = self.build_middleware_chain(self.middlewares, _process_event)
            
            try:
                await global_chain(event_object, kwargs)
            except Exception as e:
                mem_data = await memory_context.get_data()
                raise MiddlewareException(
                    middleware_title=global_chain.func.__class__.__name__, # type: ignore
                    router_id=router_id,
                    process_info=process_info,
                    memory_context={
                        'data': mem_data,
                        'state': current_state,
                    },
                    cause=e,
                ) from e

            if not is_handled:
                logger_dp.info(f'Проигнорировано: router_id: {router_id} | {process_info}')
            
        except Exception as e:
            logger_dp.exception(f'Ошибка при обработке события: router_id: {router_id} | {process_info} | {e} ')


    async def start_polling(self, bot: Bot):
        
        """
        Запускает цикл получения обновлений (long polling).

        Args:
            bot (Bot): Экземпляр бота.
        """
        
        self.polling = True
        
        await self.__ready(bot)
        
        if self.bot is None:
            raise RuntimeError('Bot не инициализирован')

        while self.polling:
                
            try:
                events: Dict = await self.bot.get_updates(marker=self.bot.marker_updates)
            except AsyncioTimeoutError:
                continue
        
            try:

                if isinstance(events, Error):
                    logger_dp.info(f'Ошибка при получении обновлений: {events}, жду {GET_UPDATES_RETRY_DELAY} секунд')
                    await asyncio.sleep(GET_UPDATES_RETRY_DELAY)
                    continue

                self.bot.marker_updates = events.get('marker')
 
                processed_events = await process_update_request(
                    events=events,
                    bot=self.bot
                )
                
                for event in processed_events:
                    if self.use_create_task:
                        asyncio.create_task(self.handle(event))
                    else:
                        await self.handle(event)
                    
            except ClientConnectorError:
                logger_dp.error(f'Ошибка подключения, жду {CONNECTION_RETRY_DELAY} секунд')
                await asyncio.sleep(CONNECTION_RETRY_DELAY)
            except Exception as e:
                logger_dp.error(f'Общая ошибка при обработке событий: {e.__class__} - {e}')

    async def handle_webhook(self, bot: Bot, host: str = 'localhost', port: int = 8080, **kwargs):
        
        """
        Запускает FastAPI-приложение для приёма обновлений через вебхук.

        Args:
            bot (Bot): Экземпляр бота.
            host (str): Хост сервера.
            port (int): Порт сервера.
        """
        
        if not FASTAPI_INSTALLED:
            raise ImportError(
                '\n\t Не установлен fastapi!'
                '\n\t Выполните команду для установки fastapi: '
                '\n\t pip install fastapi>=0.68.0'
                '\n\t Или сразу все зависимости для работы вебхука:'
                '\n\t pip install maxapi[webhook]'
            )
            
        elif not UVICORN_INSTALLED:
            raise ImportError(
                '\n\t Не установлен uvicorn!'
                '\n\t Выполните команду для установки uvicorn: '
                '\n\t pip install uvicorn>=0.15.0'
                '\n\t Или сразу все зависимости для работы вебхука:'
                '\n\t pip install maxapi[webhook]'
            )
        
        @self.webhook_post('/')
        async def _(request: Request):
            event_json = await request.json()
            event_object = await process_update_webhook(
                event_json=event_json,
                bot=bot
            )
            
            if self.use_create_task:
                asyncio.create_task(self.handle(event_object))
            else:
                await self.handle(event_object)
            return JSONResponse(content={'ok': True}, status_code=200)
        
        
        await self.init_serve(
            bot=bot,
            host=host,
            port=port, 
            **kwargs
        )
        
    async def init_serve(self, bot: Bot, host: str = 'localhost', port: int = 8080, **kwargs):
    
        """
        Запускает сервер для обработки вебхуков.

        Args:
            bot (Bot): Экземпляр бота.
            host (str): Хост.
            port (int): Порт.
        """
        
        if not UVICORN_INSTALLED:
            raise ImportError(
                '\n\t Не установлен uvicorn!'
                '\n\t Выполните команду для установки uvicorn: '
                '\n\t pip install uvicorn>=0.15.0'
                '\n\t Или сразу все зависимости для работы вебхука:'
                '\n\t pip install maxapi[webhook]'
            )
            
        if self.webhook_app is None:
            raise RuntimeError('webhook_app не инициализирован')
            
        config = Config(app=self.webhook_app, host=host, port=port, **kwargs)
        server = Server(config)
        
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
    
    def __init__(self, update_type: UpdateType, router: Dispatcher | Router):
        
        """
        Инициализирует событие-декоратор.

        Args:
            update_type (UpdateType): Тип события.
            router (Dispatcher | Router): Экземпляр роутера или диспетчера.
        """
        
        self.update_type = update_type
        self.router = router

    def __call__(self, *args, **kwargs):
        
        """
        Регистрирует функцию как обработчик события.

        Returns:
            Callable: Исходная функция.
        """
        
        def decorator(func_event: Callable):
            
            if self.update_type == UpdateType.ON_STARTED:
                self.router.on_started_func = func_event
                
            else:
                self.router.event_handlers.append(
                    Handler(
                        func_event=func_event, 
                        update_type=self.update_type,
                        *args, **kwargs
                    )
                )
            return func_event
            
        return decorator