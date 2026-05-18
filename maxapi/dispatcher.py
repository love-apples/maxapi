from __future__ import annotations

import asyncio
import functools
import inspect
import warnings
from asyncio.exceptions import TimeoutError as AsyncioTimeoutError
from collections import OrderedDict
from collections.abc import Hashable
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast
from warnings import warn

from aiohttp import ClientConnectorError

from .context import BaseContext, MemoryContext
from .enums.update import UpdateType
from .exceptions.dispatcher import HandlerException, MiddlewareException
from .exceptions.max import InvalidToken, MaxApiError, MaxConnection
from .filters import filter_attrs
from .filters.handler import Handler
from .loggers import logger_dp
from .methods.types.getted_updates import process_update_request
from .types.bot_mixin import BotMixin
from .utils.commands import extract_commands
from .utils.time import from_ms, to_ms
from .webhook import DEFAULT_HOST, DEFAULT_PATH, DEFAULT_PORT, BaseMaxWebhook
from .webhook.aiohttp import AiohttpMaxWebhook

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from magic_filter import MagicFilter

    from .bot import Bot
    from .filters.filter import BaseFilter
    from .filters.middleware import BaseMiddleware, HandlerCallable
    from .types.updates import UpdateUnion

CONNECTION_RETRY_DELAY = 30
GET_UPDATES_RETRY_DELAY = 5
CONTEXTS_MAX_SIZE = 10_000

_FilterKwargSpec = tuple[str | None, frozenset[str] | None]


@functools.lru_cache(maxsize=1024)
def _get_filter_kwarg_spec(filter_cls: Any) -> _FilterKwargSpec:
    """Возвращает имя event-аргумента и допустимые kwargs для фильтра."""
    try:
        signature = inspect.signature(filter_cls.__call__)
    except (TypeError, ValueError):
        return None, frozenset()

    params = list(signature.parameters.values())
    event_arg_name: str | None = None
    event_param_skipped = False
    allowed_kwargs: set[str] = set()

    for param in params:
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            continue

        if not event_param_skipped and param.name == "self":
            continue

        if not event_param_skipped and param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            event_arg_name = param.name
            event_param_skipped = True
            continue

        if param.kind is inspect.Parameter.VAR_KEYWORD:
            return event_arg_name, None

        if param.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            allowed_kwargs.add(param.name)

    return event_arg_name, frozenset(allowed_kwargs)


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
            router_id: Идентификатор роутера для логов.
            use_create_task: Флаг, отвечающий за параллелизацию
                обработок событий.
            storage: Класс контекста для хранения
                данных (MemoryContext, RedisContext и т.д.).
            **storage_kwargs: Дополнительные аргументы для
                инициализации хранилища.
        """

        self.router_id = router_id
        self.storage = storage
        self.storage_kwargs = storage_kwargs

        self.event_handlers: list[Handler] = []
        self.handlers_by_type: dict[UpdateType, list[Handler]] | None = None
        self.contexts: OrderedDict[
            tuple[int | None, int | None], BaseContext
        ] = OrderedDict()
        self.routers: list[Router | Dispatcher] = []
        self.filters: list[MagicFilter] = []
        self.base_filters: list[BaseFilter] = []
        self.outer_middlewares: list[BaseMiddleware] = []
        self.inner_middlewares: list[BaseMiddleware] = []

        self.bot: Bot | None = None
        self.on_started_func: Callable | None = None
        self.polling = False
        self.use_create_task = use_create_task
        self._cached_router_entries: (
            list[
                tuple[
                    Router | Dispatcher,
                    list[BaseMiddleware],
                    list[MagicFilter],
                    list[BaseFilter],
                ]
            ]
            | None
        ) = None
        self._global_mw_chain: HandlerCallable | None = None
        self._background_tasks: set[asyncio.Task] = set()
        self._ready: bool = False

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

    @property
    def middlewares(self) -> list[BaseMiddleware]:
        """
        Список outer-middleware.

        .. deprecated::
            Используйте :attr:`outer_middlewares`.
        """
        warnings.warn(
            f"{type(self).__name__}.middlewares устарел. "
            "Используйте outer_middlewares.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.outer_middlewares

    @middlewares.setter
    def middlewares(self, value: list[BaseMiddleware]) -> None:
        """
        Устанавливает outer_middlewares через устаревший атрибут.

        .. deprecated::
            Присвоение ``dp.middlewares = [...]`` устарело.
            Используйте :attr:`outer_middlewares` напрямую.
        """
        warnings.warn(
            f"{type(self).__name__}.middlewares = [...] устарел. "
            "Используйте outer_middlewares.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.outer_middlewares = value

    async def check_me(self) -> None:
        """
        Проверяет и логирует информацию о боте.
        """

        bot = self._ensure_bot()
        me = await bot.get_me()

        bot.me = me

        logger_dp.info(
            "Бот: @%s first_name=%s id=%s",
            me.username,
            me.first_name,
            me.user_id,
        )

    @staticmethod
    def build_middleware_chain(
        middlewares: list[BaseMiddleware],
        handler: HandlerCallable,
    ) -> HandlerCallable:
        """
        Формирует цепочку вызова middleware вокруг хендлера.

        Args:
            middlewares: Список middleware.
            handler: Финальный обработчик.

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
            *routers: Роутеры для добавления.
        """

        self.routers.extend(routers)

    def register_outer_middleware(self, middleware: BaseMiddleware) -> None:
        """
        Регистрирует outer middleware (до проверки фильтров handler).

        Вызывается для каждого подходящего события ещё до того, как
        диспетчер узнает, какой именно handler сработает.

        Порядок регистрации сохраняется: первый зарегистрированный
        outer middleware выполняется первым (внешний слой цепочки),
        что симметрично с :meth:`register_inner_middleware`.

        Args:
            middleware: Middleware.
        """
        self.outer_middlewares.append(middleware)

    def register_inner_middleware(self, middleware: BaseMiddleware) -> None:
        """
        Регистрирует inner middleware (после проверки фильтров handler).

        Вызывается только тогда, когда конкретный handler прошёл все
        свои фильтры и state и будет реально исполнен. На уровне
        Dispatcher — только для событий, попавших хоть в один handler;
        на уровне Router — только для handler этого роутера.

        Args:
            middleware (BaseMiddleware): Middleware.
        """
        self.inner_middlewares.append(middleware)

    def outer_middleware(self, middleware: BaseMiddleware) -> None:
        """
        Добавляет Middleware на первое место в списке outer_middlewares.

        Историческое поведение: ``insert(0, ...)``. В новом
        :meth:`register_outer_middleware` порядок изменён на ``append``
        (register order = execution order), поэтому при миграции
        проверьте порядок вызовов, если он важен.

        .. deprecated::
            Используйте :meth:`register_outer_middleware`.

        Args:
            middleware (BaseMiddleware): Middleware.
        """
        warnings.warn(
            f"{type(self).__name__}.outer_middleware() устарел. "
            "Используйте register_outer_middleware().",
            DeprecationWarning,
            stacklevel=2,
        )
        self.outer_middlewares.insert(0, middleware)

    def middleware(self, middleware: BaseMiddleware) -> None:
        """
        Добавляет Middleware в конец списка.

        .. deprecated::
            Используйте :meth:`register_outer_middleware` (текущее
            поведение — outer, до фильтров handler) или
            :meth:`register_inner_middleware` (только когда handler
            реально вызван).

        Args:
            middleware: Middleware.
        """
        warnings.warn(
            f"{type(self).__name__}.middleware() устарел. "
            "Используйте register_outer_middleware() (поведение "
            "сохраняется) или register_inner_middleware() для запуска "
            "mw только после выбора handler.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.outer_middlewares.append(middleware)

    def filter(self, base_filter: BaseFilter) -> None:
        """
        Добавляет фильтр в список.

        Args:
            base_filter: Фильтр.
        """

        self.base_filters.append(base_filter)

    async def __ready(self, bot: Bot) -> None:
        """
        Подготавливает диспетчер: сохраняет бота, подготавливает
        обработчики, вызывает on_started.

        Args:
            bot: Экземпляр бота.
        """

        if self._ready:
            return

        self.bot = bot
        self.bot.dispatcher = self

        if self.polling and bot.auto_check_subscriptions:
            await self._check_subscriptions(bot)

        await self.check_me()

        if self not in self.routers:
            self.routers.append(self)
        self._prepare_handlers(bot)

        self._global_mw_chain = self.build_middleware_chain(
            self.outer_middlewares, self._process_event
        )

        if self.on_started_func:
            await self.on_started_func()

        self._ready = True

    def _prepare_handlers(self, bot: Bot) -> None:
        """Подготовить обработчики событий и построить кеши."""

        handlers_count = 0
        global_inner_mw = self.inner_middlewares

        for router, _, accumulated_inner_mw, *_ in self._iter_unique_routers(
            self.routers, warn_duplicates=True
        ):
            router.bot = bot
            router.handlers_by_type = {}

            for handler in router.event_handlers:
                handlers_count += 1
                extract_commands(handler, bot)

                handler.func_args = frozenset(
                    inspect.signature(handler.func_event).parameters,
                )

                all_inner = (
                    global_inner_mw
                    + accumulated_inner_mw
                    + handler.middlewares
                )
                handler.mw_chain = self.build_middleware_chain(
                    all_inner,
                    functools.partial(self.call_handler, handler),
                )
                router.handlers_by_type.setdefault(
                    handler.update_type, []
                ).append(handler)

        self._cached_router_entries = self._build_dispatch_entries()

        logger_dp.info(
            "Зарегистрировано %d обработчиков событий", handlers_count
        )

    def _iter_dispatch_entries(
        self,
    ) -> Iterator[
        tuple[
            Router | Dispatcher,
            list[BaseMiddleware],
            list[MagicFilter],
            list[BaseFilter],
        ]
    ]:
        """Ленивый генератор entries для dispatch.

        Используется когда ``_ready=False`` — позволяет остановить обход
        дерева роутеров сразу после первого совпадения, не аллоцируя
        полный список.  Inner-middleware уже выпечены в
        ``handler.mw_chain`` в :meth:`_prepare_handlers`, поэтому в
        кортеж попадают только ``(router, outer_mw, filters,
        base_filters)``.
        """
        for (
            router,
            outer_mw,
            _inner_mw,
            filters,
            base_filters,
        ) in self._iter_unique_routers(self.routers):
            yield router, outer_mw, filters, base_filters

    def _build_dispatch_entries(
        self,
    ) -> list[
        tuple[
            Router | Dispatcher,
            list[BaseMiddleware],
            list[MagicFilter],
            list[BaseFilter],
        ]
    ]:
        """Материализует полный список entries для кеша горячего пути.

        Вызывается один раз при ``_ready=True`` и результат сохраняется в
        ``_cached_router_entries``. Для ``_ready=False`` используйте
        :meth:`_iter_dispatch_entries`.
        """
        return list(self._iter_dispatch_entries())

    @staticmethod
    async def _check_subscriptions(bot: Bot) -> None:
        """Проверить наличие подписок при запуске polling."""
        response = await bot.get_subscriptions()

        if subscriptions := response.subscriptions:
            logger_subscriptions_text = ", ".join(
                [s.url for s in subscriptions]
            )
            logger_dp.warning(
                "БОТ ИГНОРИРУЕТ POLLING! "
                "Обнаружены установленные подписки: %s",
                logger_subscriptions_text,
            )

    def __get_context(
        self, chat_id: int | None, user_id: int | None
    ) -> BaseContext:
        """
        Возвращает существующий или создаёт новый контекст
        по chat_id и user_id.

        Args:
            chat_id: Идентификатор чата.
            user_id: Идентификатор пользователя.

        Returns:
            BaseContext: Контекст.
        """

        key = (chat_id, user_id)
        ctx = self.contexts.get(key)
        if ctx is not None:
            if ctx.is_ttl_expired():
                logger_dp.debug("Истёк TTL контекста %s", key)
                del self.contexts[key]
            else:
                ctx.touch_ttl()
                # Перемещаем в конец, чтобы LRU-вытеснение удаляло
                # самые давно неиспользованные контексты
                self.contexts.move_to_end(key)
                return ctx

        if len(self.contexts) >= CONTEXTS_MAX_SIZE:
            evicted_key = next(iter(self.contexts))
            logger_dp.debug(
                "Вытеснен контекст %s (лимит %d)",
                evicted_key,
                CONTEXTS_MAX_SIZE,
            )
            self.contexts.popitem(last=False)

        new_ctx = self.storage(chat_id, user_id, **self.storage_kwargs)
        new_ctx.touch_ttl()
        self.contexts[key] = new_ctx
        return new_ctx

    @staticmethod
    async def call_handler(
        handler: Handler,
        event_object: UpdateUnion | dict[str, Any],
        data: dict[str, Any],
    ) -> None:
        """
        Вызывает хендлер с нужными аргументами.

        Перед вызовом фильтрует ``data``, оставляя только те ключи,
        которые handler реально принимает (по ``handler.func_args`` или
        параметрам, полученным через :func:`inspect.signature`).
        В отличие от ``get_annotations``, ``signature`` не включает
        ``"return"`` и не требует eval строковых аннотаций — безопасен
        при ``from __future__ import annotations``. Несовместимые ключи
        не дойдут до handler и не приведут к ``TypeError``.

        Args:
            handler: Handler.
            event_object: Объект события.
            data: Данные, накопленные фильтрами и middleware.

        Returns:
            None
        """
        if data:
            func_args = handler.func_args or frozenset(
                inspect.signature(handler.func_event).parameters,
            )
            kwargs = {k: v for k, v in data.items() if k in func_args}
            if kwargs:
                await handler.func_event(event_object, **kwargs)
                return

        await handler.func_event(event_object)

    @staticmethod
    def _resolve_filter_kwargs(
        base_filter: BaseFilter, data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Подбирает kwargs для BaseFilter по сигнатуре ``__call__``.
        """
        event_arg_name, allowed_kwargs = _get_filter_kwarg_spec(
            cast(Hashable, type(base_filter))
        )

        if allowed_kwargs is None:
            return {
                key: value
                for key, value in data.items()
                if key != event_arg_name
            }

        return {
            key: value for key, value in data.items() if key in allowed_kwargs
        }

    @staticmethod
    async def process_base_filters(
        event: UpdateUnion,
        filters: list[BaseFilter],
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Асинхронно применяет фильтры к событию.

        Args:
            event: Событие.
            filters: Список фильтров.

        Returns:
            dict[str, Any] | None: Словарь с результатом или None,
                если фильтр не прошёл.
        """

        available_data: dict[str, Any] = dict(data or {})
        filter_data: dict[str, Any] = {}

        for _filter in filters:
            kwargs = Dispatcher._resolve_filter_kwargs(_filter, available_data)
            result = await _filter(event, **kwargs)

            if isinstance(result, dict):
                filter_data.update(result)
                available_data.update(result)

            elif not result:
                return None

        return filter_data

    def _iter_routers(
        self,
        routers: list[Router | Dispatcher],
        parent_outer_middlewares: list[BaseMiddleware] | None = None,
        parent_inner_middlewares: list[BaseMiddleware] | None = None,
        parent_filters: list[MagicFilter] | None = None,
        parent_base_filters: list[BaseFilter] | None = None,
        path: set[int] | None = None,
    ) -> Iterator[
        tuple[
            Router | Dispatcher,
            list[BaseMiddleware],
            list[BaseMiddleware],
            list[MagicFilter],
            list[BaseFilter],
        ]
    ]:
        """
        Рекурсивно обходит роутеры, накапливая middleware и фильтры родителей.

        Args:
            routers: Список роутеров для обхода.
            parent_outer_middlewares: Накопленные outer middleware от
                родительских роутеров.
            parent_inner_middlewares: Накопленные inner middleware от
                родительских роутеров.
            parent_filters: Накопленные MagicFilter от родительских
                роутеров.
            parent_base_filters: Накопленные BaseFilter от родительских
                роутеров.
            path: Идентификаторы роутеров в текущей ветви обхода; используется,
                чтобы не уходить в бесконечную рекурсию при циклических
                включениях между роутерами.

        Yields:
            Кортеж (роутер, outer_mw, inner_mw, MagicFilter, BaseFilter)
            с накопленными значениями от всех родителей.
        """
        outer_middlewares = parent_outer_middlewares or []
        inner_middlewares = parent_inner_middlewares or []
        filters = parent_filters or []
        base_filters = parent_base_filters or []

        if path is None:
            path = set()

        for router in routers:
            router_key = id(router)
            if router_key in path:
                continue

            accumulated_outer_middlewares: list[BaseMiddleware]
            if router is self:
                accumulated_outer_middlewares = outer_middlewares
                accumulated_inner_middlewares: list[BaseMiddleware] = (
                    inner_middlewares
                )
            else:
                accumulated_outer_middlewares = (
                    outer_middlewares + router.outer_middlewares
                )
                accumulated_inner_middlewares = (
                    inner_middlewares + router.inner_middlewares
                )

            accumulated_filters = filters + router.filters
            accumulated_base_filters = base_filters + router.base_filters

            yield (
                router,
                accumulated_outer_middlewares,
                accumulated_inner_middlewares,
                accumulated_filters,
                accumulated_base_filters,
            )

            sub_routers = (
                []
                if router is self
                else [r for r in router.routers if r is not self]
            )
            if sub_routers:
                path.add(router_key)
                try:
                    yield from self._iter_routers(
                        routers=sub_routers,
                        parent_outer_middlewares=(
                            accumulated_outer_middlewares
                        ),
                        parent_inner_middlewares=(
                            accumulated_inner_middlewares
                        ),
                        parent_filters=accumulated_filters,
                        parent_base_filters=accumulated_base_filters,
                        path=path,
                    )
                finally:
                    path.discard(router_key)

    def _iter_unique_routers(
        self,
        routers: list[Router | Dispatcher],
        parent_outer_middlewares: list[BaseMiddleware] | None = None,
        parent_inner_middlewares: list[BaseMiddleware] | None = None,
        parent_filters: list[MagicFilter] | None = None,
        parent_base_filters: list[BaseFilter] | None = None,
        *,
        warn_duplicates: bool = False,
    ) -> Iterator[
        tuple[
            Router | Dispatcher,
            list[BaseMiddleware],
            list[BaseMiddleware],
            list[MagicFilter],
            list[BaseFilter],
        ]
    ]:
        """
        Обходит дерево роутеров и исключает повторные экземпляры роутеров.

        При повторном включении одного и того же объекта роутера используется
        контекст первого вхождения (накопленные middleware и фильтры).

        Args:
            routers: Список роутеров для обхода.
            parent_outer_middlewares: Накопленные outer middleware от
                родительских роутеров.
            parent_inner_middlewares: Накопленные inner middleware от
                родительских роутеров.
            parent_filters: Накопленные MagicFilter от родительских
                роутеров.
            parent_base_filters: Накопленные BaseFilter от родительских
                роутеров.
            warn_duplicates: Если True, выводит предупреждение при обнаружении
                повторных включений одного и того же экземпляра роутера.
        """
        seen: set[int] = set()
        duplicate_keys: set[int] = set()
        duplicate_titles: list[str] = []
        try:
            for item in self._iter_routers(
                routers=routers,
                parent_outer_middlewares=parent_outer_middlewares,
                parent_inner_middlewares=parent_inner_middlewares,
                parent_filters=parent_filters,
                parent_base_filters=parent_base_filters,
            ):
                router = item[0]
                router_key = id(router)
                if router_key in seen:
                    if warn_duplicates and router_key not in duplicate_keys:
                        duplicate_keys.add(router_key)
                        rid = getattr(router, "router_id", None)
                        router_title = (
                            str(rid)
                            if rid is not None
                            else router.__class__.__name__
                        )
                        duplicate_titles.append(router_title)
                    continue
                seen.add(router_key)
                yield item
        finally:
            if warn_duplicates and duplicate_titles:
                logger_dp.warning(
                    "Обнаружены повторные включения роутеров: %s. "
                    "Повторные вхождения будут дедуплицированы.",
                    ", ".join(duplicate_titles),
                )

    async def _check_router_filters(
        self,
        event: UpdateUnion,
        filters: list[MagicFilter],
        base_filters: list[BaseFilter],
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Проверяет накопленные фильтры роутера для события.

        Args:
            event: Событие.
            filters: Накопленные MagicFilter.
            base_filters: Накопленные BaseFilter.

        Returns:
            dict[str, Any] | None: Словарь с данными или None,
                если фильтры не прошли.
        """
        if filters and not filter_attrs(event, *filters):
            return None

        if base_filters:
            return await self.process_base_filters(
                event=event, filters=base_filters, data=data
            )

        return {}

    @staticmethod
    def _find_matching_handlers(
        router: Router | Dispatcher, event_type: UpdateType
    ) -> list[Handler]:
        """
        Находит обработчики, соответствующие типу события в роутере.

        Args:
            router: Роутер для поиска.
            event_type: Тип события.

        Returns:
            List[Handler]: Список подходящих обработчиков.
        """
        index = router.handlers_by_type
        if index is not None:
            return index.get(event_type, [])

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
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Проверяет, подходит ли обработчик для события (фильтры, состояние).

        Args:
            handler: Обработчик для проверки.
            event: Событие.
            current_state: Текущее состояние.

        Returns:
            dict[str, Any] | None: Словарь с данными или None,
                если не подходит.
        """
        check_data = dict(data or {})
        check_data.setdefault("raw_state", current_state)

        handler_data: dict[str, Any] = {}

        if handler.states and handler.state_filter is None:
            handler.prepare_state_filter()

        if handler.state_filter is not None:
            state_result = await self.process_base_filters(
                event=event,
                filters=[handler.state_filter],
                data=check_data,
            )
            if state_result is None:
                return None
            handler_data.update(state_result)
            check_data.update(state_result)

        filter_result = await self._check_router_filters(
            event=event,
            filters=handler.filters,
            base_filters=handler.base_filters,
            data=check_data,
        )
        if filter_result is None:
            return None

        handler_data.update(filter_result)
        return handler_data

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
            handler: Обработчик для выполнения.
            event: Событие.
            data: Данные для обработчика.
            handler_middlewares: Middleware для
                обработчика.
            memory_context: Контекст памяти.
            current_state: Текущее состояние.
            router_id: Идентификатор роутера для логов.
            process_info: Информация о процессе для логов.

        Raises:
            HandlerException: При ошибке выполнения обработчика.
        """
        handler_chain = handler.mw_chain or self.build_middleware_chain(
            handler_middlewares,
            functools.partial(self.call_handler, handler),
        )

        try:
            await handler_chain(event, data)
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
        entries = (
            self._cached_router_entries
            if self._cached_router_entries is not None
            else self._iter_unique_routers(self.routers)
        )
        for router, *_ in entries:
            matching_handlers = self._find_matching_handlers(
                router=router,
                event_type=event_type,
            )
            for handler in matching_handlers:
                try:
                    await self.call_handler(
                        handler=handler,
                        event_object=raw_data,
                        data={},
                    )
                except Exception as e:  # noqa: PERF203
                    logger_dp.exception(
                        "Ошибка в обработчике RAW_API_RESPONSE: %r", e
                    )

    async def _run_router_handlers(
        self,
        event: UpdateUnion,
        data: dict[str, Any],
        matching_handlers: list[Handler],
        memory_context: BaseContext,
        current_state: Any | None,
        router_id: Any,
        process_info: str,
    ) -> bool:
        """
        Перебирает обработчики роутера и выполняет первый подходящий.

        Returns:
            bool: True если обработчик был выполнен.
        """
        for handler in matching_handlers:
            handler_match_result = await self._check_handler_match(
                handler=handler,
                event=event,
                current_state=current_state,
                data=data,
            )
            if handler_match_result is None:
                continue
            data.update(handler_match_result)
            await self._execute_handler(
                handler=handler,
                event=event,
                data=data,
                handler_middlewares=handler.middlewares,
                memory_context=memory_context,
                current_state=current_state,
                router_id=router_id,
                process_info=process_info,
            )
            logger_dp.info(
                "Обработано: router_id: %s | %s", router_id, process_info
            )
            return True
        return False

    async def _invoke_router_handlers(
        self,
        event: UpdateUnion,
        handler_data: dict[str, Any],
        *,
        matching_handlers: list[Handler],
        memory_context: BaseContext,
        current_state: Any | None,
        router_id: Any,
        process_info: str,
    ) -> None:
        """
        Endpoint middleware-цепочки роутера: вызывает подходящий обработчик.

        Args:
            event: Событие.
            handler_data: Данные для обработчика.
            matching_handlers: Обработчики роутера для данного типа события.
            memory_context: Контекст памяти.
            current_state: Текущее состояние.
            router_id: Идентификатор роутера для логов.
            process_info: Информация о процессе для логов.
        """
        if await self._run_router_handlers(
            event=event,
            data=handler_data,
            matching_handlers=matching_handlers,
            memory_context=memory_context,
            current_state=current_state,
            router_id=router_id,
            process_info=process_info,
        ):
            handler_data["_handled"] = True

    async def _dispatch_to_router(
        self,
        event_object: UpdateUnion,
        data: dict[str, Any],
        matching_handlers: list[Handler],
        router_outer_middlewares: list[BaseMiddleware],
        memory_context: BaseContext,
        current_state: Any | None,
        router_id: Any,
        process_info: str,
    ) -> bool:
        """
        Диспатчит событие через outer middleware одного роутера.

        Inner middleware к моменту вызова уже выпечены в
        ``handler.mw_chain`` (см. :meth:`_prepare_handlers`).

        Returns:
            bool: True если событие было обработано.
        """
        data["_handled"] = False

        process_fn = functools.partial(
            self._invoke_router_handlers,
            matching_handlers=matching_handlers,
            memory_context=memory_context,
            current_state=current_state,
            router_id=router_id,
            process_info=process_info,
        )

        if router_outer_middlewares:
            chain = self.build_middleware_chain(
                router_outer_middlewares, process_fn
            )
            await chain(event_object, data)
        else:
            await process_fn(event_object, data)

        return data.pop("_handled", False)

    async def _iter_and_dispatch_routers(
        self,
        event_object: UpdateUnion,
        data: dict[str, Any],
        memory_context: BaseContext,
        current_state: Any | None,
        process_info: str,
    ) -> tuple[Any, bool]:
        """
        Перебирает все роутеры и диспетчеризует событие.

        Returns:
            tuple[Any, bool]: (router_id, is_handled)
        """
        router_id = None

        entries: Iterable[
            tuple[
                Router | Dispatcher,
                list[BaseMiddleware],
                list[MagicFilter],
                list[BaseFilter],
            ]
        ]
        if self._ready:
            if self._cached_router_entries is None:
                self._cached_router_entries = self._build_dispatch_entries()
            entries = self._cached_router_entries
        else:
            entries = self._iter_dispatch_entries()

        for (
            router,
            router_outer_middlewares,
            router_filters,
            router_base_filters,
        ) in entries:
            router_id = router.router_id or id(router)

            router_filter_result = await self._check_router_filters(
                event=event_object,
                filters=router_filters,
                base_filters=router_base_filters,
                data=data,
            )
            if router_filter_result is None:
                continue
            data.update(router_filter_result)

            matching_handlers = self._find_matching_handlers(
                router=router,
                event_type=event_object.update_type,
            )
            if not matching_handlers:
                continue

            if await self._dispatch_to_router(
                event_object=event_object,
                data=data,
                matching_handlers=matching_handlers,
                router_outer_middlewares=router_outer_middlewares,
                memory_context=memory_context,
                current_state=current_state,
                router_id=router_id,
                process_info=process_info,
            ):
                return router_id, True

        return router_id, False

    def _on_background_task_done(self, task: asyncio.Task) -> None:
        """Callback завершения фоновой задачи (use_create_task=True).

        Удаляет задачу из пула и логирует необработанное исключение, если оно
        есть. Без явного вызова ``task.exception()`` Python при сборке мусора
        выдаст предупреждение *"Task exception was never retrieved"*.
        """
        self._background_tasks.discard(task)
        if not task.cancelled():
            exc = task.exception()
            if exc is not None:
                logger_dp.exception(
                    "Необработанное исключение в фоновой задаче handle(): %r",
                    exc,
                )

    @staticmethod
    def _get_middleware_title(chain: Any) -> str:
        """Определяет имя middleware для диагностики."""
        if hasattr(chain, "func"):
            return str(chain.func.__class__.__name__)
        return str(getattr(chain, "__name__", chain.__class__.__name__))

    async def _process_event(
        self,
        event_object: UpdateUnion,
        data: dict[str, Any],
    ) -> None:
        """
        Endpoint глобальной middleware-цепочки: диспатчит событие
        по роутерам.

        Args:
            event_object: Событие.
            data: Данные от middleware-цепочки,
                содержащие ``_memory_context``, ``_current_state``
                и ``_process_info``.
        """
        memory_context = data["_memory_context"]
        data["context"] = memory_context
        data["raw_state"] = data["_current_state"]

        router_id, is_handled = await self._iter_and_dispatch_routers(
            event_object=event_object,
            data=data,
            memory_context=memory_context,
            current_state=data["_current_state"],
            process_info=data["_process_info"],
        )
        data["_router_id"] = router_id
        data["_is_handled"] = is_handled

    async def handle(self, event_object: UpdateUnion) -> None:
        """
        Основной обработчик события. Применяет фильтры, middleware
        и вызывает нужный handler.

        Args:
            event_object: Событие.
        """
        router_id = None
        process_info = "нет данных"

        try:
            ids = event_object.get_ids()
            memory_context = self.__get_context(*ids)
            current_state = await memory_context.get_state()

            process_info = (
                f"{event_object.update_type} | "
                f"chat_id: {ids[0]}, user_id: {ids[1]}"
            )

            kwargs: dict[str, Any] = {
                "context": memory_context,
                "raw_state": current_state,
                "_memory_context": memory_context,
                "_current_state": current_state,
                "_process_info": process_info,
            }

            global_chain = (
                self._global_mw_chain
                or self.build_middleware_chain(
                    self.outer_middlewares, self._process_event
                )
            )

            try:
                await global_chain(event_object, kwargs)
            except Exception as e:
                mem_data = await memory_context.get_data()

                raise MiddlewareException(
                    middleware_title=self._get_middleware_title(global_chain),
                    router_id=kwargs.get("_router_id", router_id),
                    process_info=process_info,
                    memory_context={
                        "data": mem_data,
                        "state": current_state,
                    },
                    cause=e,
                ) from e

            router_id = kwargs.get("_router_id")
            is_handled = kwargs.get("_is_handled", False)

            if not is_handled:
                logger_dp.info(
                    "Проигнорировано: router_id: %s | %s",
                    router_id,
                    process_info,
                )

        except Exception as e:
            logger_dp.exception(
                "Ошибка при обработке события: router_id: %s | %s | %r",
                router_id,
                process_info,
                e,
            )

    async def _fetch_updates_once(self, bot: Bot) -> dict | None:
        """
        Делает один запрос get_updates.

        Returns:
            dict | None: словарь событий или None при recoverable-ошибке.

        Raises:
            InvalidToken: при неверном токене бота.
        """
        try:
            return await bot.get_updates(marker=bot.marker_updates)
        except AsyncioTimeoutError:
            return None
        except (MaxConnection, ClientConnectorError) as e:
            logger_dp.warning(
                "Ошибка подключения при получении обновлений: %r, "
                "жду %s секунд",
                e,
                CONNECTION_RETRY_DELAY,
            )
            await asyncio.sleep(CONNECTION_RETRY_DELAY)
            return None
        except InvalidToken:
            logger_dp.error("Неверный токен! Останавливаю polling")
            self.polling = False
            raise
        except MaxApiError as e:
            logger_dp.info(
                "Ошибка при получении обновлений: %r, жду %s секунд",
                e,
                GET_UPDATES_RETRY_DELAY,
            )
            await asyncio.sleep(GET_UPDATES_RETRY_DELAY)
            return None
        except Exception as e:
            logger_dp.error(
                "Неожиданная ошибка при получении обновлений: %r",
                e,
            )
            await asyncio.sleep(GET_UPDATES_RETRY_DELAY)
            return None

    async def _dispatch_fetched_events(
        self,
        events: dict,
        current_timestamp: int,
        *,
        skip_updates: bool,
    ) -> None:
        """Обрабатывает полученные от API события."""
        try:
            bot = self._ensure_bot()
            bot.marker_updates = events.get("marker")

            processed_events = await process_update_request(
                events=events, bot=bot
            )

            for event in processed_events:
                if skip_updates and event.timestamp < current_timestamp:
                    logger_dp.info(
                        "Пропуск события от %s: %s",
                        from_ms(event.timestamp),
                        event.update_type,
                    )
                    continue

                if self.use_create_task:
                    task = asyncio.create_task(self.handle(event))
                    self._background_tasks.add(task)
                    task.add_done_callback(self._on_background_task_done)
                else:
                    await self.handle(event)

        except ClientConnectorError:
            logger_dp.error(
                "Ошибка подключения, жду %s секунд", CONNECTION_RETRY_DELAY
            )
            await asyncio.sleep(CONNECTION_RETRY_DELAY)
        except Exception as e:
            logger_dp.error(
                "Общая ошибка при обработке событий: %r",
                e,
            )

    async def start_polling(
        self, bot: Bot, *, skip_updates: bool = False
    ) -> None:
        """
        Запускает цикл получения обновлений (long polling).

        Args:
            bot: Экземпляр бота.
            skip_updates: Флаг, отвечающий за обработку старых событий.
        """
        self.polling = True

        await self.__ready(bot)

        current_timestamp = to_ms(datetime.now())

        while self.polling:
            events = await self._fetch_updates_once(bot)
            if events is None:
                continue
            await self._dispatch_fetched_events(
                events, current_timestamp, skip_updates=skip_updates
            )

    async def stop_polling(self) -> None:
        """
        Останавливает цикл получения обновлений (long polling).

        Дожидается завершения всех фоновых задач (use_create_task=True),
        запущенных до момента остановки.
        """
        if self.polling:
            self.polling = False
            self._ready = False
            logger_dp.info("Polling остановлен")

        if self._background_tasks:
            logger_dp.info(
                "Ожидаю завершения %d фоновых задач...",
                len(self._background_tasks),
            )
            await asyncio.gather(
                *self._background_tasks, return_exceptions=True
            )
            logger_dp.info("Все фоновые задачи завершены")

    async def startup(self, bot: Bot) -> None:
        """
        Инициализирует диспетчер: сохраняет бота, подготавливает
        обработчики и вызывает on_started.

        Используется интеграционными модулями (например,
        maxapi.webhook.fastapi) для инициализации в lifespan
        веб-фреймворка.

        Args:
            bot: Экземпляр бота.
        """
        await self.__ready(bot)

    async def handle_webhook(
        self,
        bot: Bot,
        *,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        path: str = DEFAULT_PATH,
        secret: str | None = None,
        webhook_type: type[BaseMaxWebhook] = AiohttpMaxWebhook,
        **kwargs: Any,
    ) -> None:
        """
        Запускает вебхук-сервер (aiohttp) для приёма обновлений.

        Удобный метод «всё в одном»: создаёт aiohttp-приложение через
        :class:`~maxapi.webhook.aiohttp.BaseMaxWebhook`,
        регистрирует маршрут и запускает сервер.

        Для более гибкого управления жизненным циклом сервера используйте
        одну из реализаций BaseMaxWebhook напрямую, например
        :class:`~maxapi.webhook.aiohttp.BaseMaxWebhook`.

        Args:
            bot: Экземпляр бота.
            host: Хост сервера (по умолчанию ``"0.0.0.0"``).
            port: Порт сервера (по умолчанию ``8080``).
            path: URL-путь для маршрута вебхука.
            secret: Секрет для проверки заголовка
                ``X-Max-Bot-Api-Secret``. Должен совпадать со значением,
                переданным в :meth:`~maxapi.Bot.subscribe_webhook`.
            webhook_type: Класс вебхука.
            **kwargs: Дополнительные аргументы для ``aiohttp.web.AppRunner``.
        """
        webhook = webhook_type(dp=self, bot=bot, secret=secret)
        await webhook.run(host=host, port=port, path=path, **kwargs)

    async def init_serve(  # pragma: no cover
        self,
        bot: Bot,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        **kwargs: Any,
    ) -> None:
        """
        .. deprecated::
            Используйте :meth:`handle_webhook` вместо ``init_serve``.
            Метод будет удалён в одной из следующих версий.

        Args:
            bot: Экземпляр бота.
            host: Хост.
            port: Порт.
        """
        warn(
            "init_serve устарел и будет удалён в следующих версиях. "
            "Используйте handle_webhook вместо него.",
            DeprecationWarning,
            stacklevel=2,
        )
        await self.handle_webhook(bot, host=host, port=port, **kwargs)


class Router(Dispatcher):
    """
    Роутер для группировки обработчиков событий.
    """

    def __init__(self, router_id: str | None = None):
        """
        Инициализация роутера.

        Args:
            router_id: Идентификатор роутера для логов.
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
            update_type: Тип события.
            router: Экземпляр роутера или диспетчера.
            deprecated: Флаг, указывающий на то, что событие устарело.
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
            func_event: Функция-обработчик
            *args: Фильтры
            **kwargs: Дополнительные параметры (например, states)

        Returns:
            Callable: Исходная функция.
        """

        if self.deprecated:
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
