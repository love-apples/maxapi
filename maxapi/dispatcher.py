from __future__ import annotations

import asyncio
import functools
import inspect
import warnings
import weakref
from asyncio.exceptions import TimeoutError as AsyncioTimeoutError
from collections import OrderedDict
from collections.abc import Hashable
from contextlib import suppress
from contextvars import ContextVar
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast
from warnings import warn

from aiohttp import ClientConnectorError
from magic_filter import MagicFilter

from .context import BaseContext, ContextManager, MemoryContext
from .context.isolation import BaseEventIsolation, DisabledEventIsolation
from .enums.update import UpdateType
from .exceptions.dispatcher import HandlerException, MiddlewareException
from .exceptions.max import InvalidToken, MaxApiError, MaxConnection
from .filters import filter_attrs
from .filters.handler import ErrorHandler, Handler
from .loggers import logger_dp
from .methods.types.getted_updates import process_update_request
from .types.bot_mixin import BotMixin
from .types.error_event import ErrorEvent as ErrorEventObject
from .utils.commands import extract_commands
from .utils.time import from_ms, to_ms
from .webhook import DEFAULT_HOST, DEFAULT_PATH, DEFAULT_PORT, BaseMaxWebhook
from .webhook.aiohttp import AiohttpMaxWebhook

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator

    from .bot import Bot
    from .filters.filter import BaseFilter
    from .filters.middleware import BaseMiddleware, HandlerCallable
    from .types.updates import UpdateUnion

CONNECTION_RETRY_DELAY = 30
GET_UPDATES_RETRY_DELAY = 5
CONTEXTS_MAX_SIZE = 10_000

_FilterKwargSpec = tuple[str | None, frozenset[str] | None]

_in_handler: ContextVar[bool] = ContextVar("maxapi_in_handler", default=False)
"""Признак того, что текущая задача выполняет :meth:`Dispatcher.handle`.

Нужен :meth:`Dispatcher.shutdown`, чтобы распознать реентрантный вызов
(обработчик остановил диспетчер сам) и не дожидаться задач, которые ждут
этот же обработчик. Метка наследуется в ``create_task`` и общая для всех
диспетчеров процесса, поэтому одной её мало: ``shutdown`` дополнительно
проверяет, что текущая задача принадлежит именно ему.
"""


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
        event_isolation: BaseEventIsolation | None = None,
        **storage_kwargs: Any,
    ) -> None:
        """
        Инициализация диспетчера.

        Args:
            router_id: Идентификатор роутера для логов.
            use_create_task: Флаг, отвечающий за параллелизацию
                обработок событий.
            event_isolation: Изоляция обработки событий: сериализует
                конкурентные апдейты одного пользователя
                (см. :class:`~maxapi.context.SimpleEventIsolation`).
                По умолчанию отключена
                (:class:`~maxapi.context.DisabledEventIsolation`).
            storage: Класс контекста для хранения
                данных (MemoryContext, RedisContext и т.д.).
            **storage_kwargs: Дополнительные аргументы для
                инициализации хранилища.
        """

        self.router_id = router_id
        self.storage = storage
        self.storage_kwargs = storage_kwargs
        self.event_isolation: BaseEventIsolation = (
            event_isolation
            if event_isolation is not None
            else DisabledEventIsolation()
        )
        self._fsm = ContextManager(self, self.__get_context)

        self.event_handlers: list[Handler] = []
        self.error_handlers: list[ErrorHandler] = []
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
        self._closing: bool = False
        self._deferred_shutdown: bool = False
        self._polling_task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None
        self._ready: bool = False
        self._parents: weakref.WeakSet[Dispatcher] = weakref.WeakSet()
        self._handlers_dirty: bool = False
        self._warned_duplicate_routers: weakref.WeakSet[
            Router | Dispatcher
        ] = weakref.WeakSet()

        self.message_created = Event(
            update_type=UpdateType.MESSAGE_CREATED, router=self
        )
        self.errors = ErrorEventObserver(router=self)
        self.error = self.errors
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
    def fsm(self) -> ContextManager:
        """
        Менеджер FSM-контекстов диспетчера.
        """
        return self._fsm

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
        self._invalidate_handlers()

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

        Можно вызывать и после старта: индекс обработчиков будет
        перестроен перед следующей диспетчеризацией, тогда же у
        добавленного роутера появится ``router.bot`` (до этого он
        остаётся ``None``).

        Порядок обхода сохраняется: включённые роутеры проверяются
        раньше собственных обработчиков диспетчера — в том числе при
        позднем включении, когда сам диспетчер уже добавлен в конец
        ``self.routers`` (см. :meth:`__ready`).

        Прямая мутация ``dp.routers`` (``dp.routers.append(...)``)
        индекс устаревшим не помечает: изменения попадут в
        диспетчеризацию лишь при следующей перестройке, вызванной
        другой регистрацией, а добавленный так роутер окажется после
        собственных обработчиков диспетчера. Используйте этот метод.

        Args:
            *routers: Роутеры для добавления.
        """

        if self in self.routers:
            # Сам диспетчер стоит последним: новые роутеры должны
            # попасть перед ним, иначе поздно включённый роутер
            # получал бы событие после хендлеров самого dp.
            position = self.routers.index(self)
            self.routers[position:position] = routers
        else:
            self.routers.extend(routers)

        for router in routers:
            router._parents.add(self)  # noqa: SLF001

        self._invalidate_handlers()

    def _invalidate_handlers(self, _seen: set[int] | None = None) -> None:
        """
        Помечает индекс обработчиков устаревшим и уведомляет родителей.

        Вызывается при регистрации через публичные методы: хендлера,
        роутера, middleware или фильтра. Прямые мутации списков
        (``routers``, ``filters``, ``outer_middlewares`` и т.п.) сюда не
        попадают и индексом не отслеживаются. Сам индекс
        перестраивается лениво, перед следующей диспетчеризацией
        (см. :meth:`_ensure_prepared`).

        Вместе с кешем записей сбрасывается и ``handlers_by_type``:
        иначе неподготовленный диспетчер (``bot is None``) на ленивом
        пути читал бы устаревший индекс роутера, построенный другим
        диспетчером.

        Args:
            _seen: Идентификаторы уже посещённых роутеров. Защищает от
                зацикливания при взаимных включениях. Ранний выход по
                самому флагу ``_handlers_dirty`` не годится: у детей он
                никогда не сбрасывается, и следующая инвалидация не
                дошла бы до корня.
        """

        seen = set() if _seen is None else _seen
        if id(self) in seen:
            return
        seen.add(id(self))

        self._handlers_dirty = True
        self._cached_router_entries = None
        self.handlers_by_type = None

        for parent in self._parents:
            parent._invalidate_handlers(seen)  # noqa: SLF001

    def _ensure_prepared(self) -> None:
        """
        Перестраивает индекс обработчиков, если были поздние регистрации.

        Условие перестройки не зависит от ``_ready``: после
        :meth:`stop_polling` диспетчер уже не «готов», но индекс с
        прошлого запуска остаётся и должен учитывать новые регистрации.
        Единственное требование — известный ``bot``: до первого старта
        перестраивать нечем, и диспетчеризация идёт по ленивому пути.

        Метод синхронный: между проверкой флага и перестройкой нет точек
        переключения event loop, поэтому диспетчеризация никогда не
        видит полуготовый индекс.
        """

        bot = self.bot
        if not self._handlers_dirty or bot is None:
            return

        self._prepare_handlers(bot, rebuild=True)
        self._global_mw_chain = self.build_middleware_chain(
            self.outer_middlewares, self._process_event
        )

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
        self._invalidate_handlers()

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
        self._invalidate_handlers()

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
        self._invalidate_handlers()

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
        self._invalidate_handlers()

    def filter(self, base_filter: MagicFilter | BaseFilter) -> None:
        """
        Добавляет фильтр уровня роутера.

        Принимает как :class:`~magic_filter.MagicFilter`
        (``F.chat.type == ChatType.DIALOG``), так и
        :class:`~maxapi.filters.filter.BaseFilter`: тип определяется по
        значению и фильтр попадает в ``filters`` или ``base_filters``
        соответственно.

        Можно вызывать и после старта. Прямая мутация списков
        (``router.filters.append(...)``) индекс устаревшим не
        помечает: добавленный так фильтр начнёт действовать лишь
        после перестройки, вызванной другой регистрацией. Используйте
        этот метод.

        Args:
            base_filter: Фильтр.
        """

        if isinstance(base_filter, MagicFilter):
            self.filters.append(base_filter)
        else:
            self.base_filters.append(base_filter)

        self._invalidate_handlers()

    async def __ready(self, bot: Bot) -> None:
        """
        Подготавливает диспетчер: сохраняет бота, подготавливает
        обработчики, вызывает on_started.

        Args:
            bot: Экземпляр бота.
        """

        # Сбрасываем признак завершения до раннего выхода: повторный
        # startup() после shutdown() (webhook-сценарий) не проходит
        # подготовку заново, но диспетчер снова принимает события.
        self._closing = False

        if self._ready:
            # Регистрации между shutdown() и повторным startup() должны
            # попасть в индекс сразу: подготовка не повторяется, а
            # bot.commands обязан быть актуален уже до первого события.
            self._ensure_prepared()
            return

        self.bot = bot
        self.bot.dispatcher = self

        # Сам диспетчер добавляем в роутеры до сетевых await'ов ниже:
        # событие, пришедшее в окно подготовки, вызовет перестройку
        # индекса, и без этого его собственные обработчики в неё
        # не попадут.
        if self not in self.routers:
            self.routers.append(self)

        if self.polling and bot.auto_check_subscriptions:
            await self._check_subscriptions(bot)

        await self.check_me()

        self._prepare_handlers(bot)

        self._global_mw_chain = self.build_middleware_chain(
            self.outer_middlewares, self._process_event
        )

        if self.on_started_func:
            await self.on_started_func()

        # Регистрации внутри on_started попадают в индекс сразу,
        # чтобы первое же событие не платило за перестройку.
        self._ensure_prepared()

        self._ready = True

    def _prepare_handlers(self, bot: Bot, *, rebuild: bool = False) -> None:
        """Подготовить обработчики событий и построить кеши.

        ``bot.commands`` целиком принадлежит диспетчеру и на каждой
        подготовке производится заново из дерева обработчиков ЭТОГО
        диспетчера, поэтому список очищается в начале: иначе повторный
        ``startup()`` или перестройка индекса дублировали бы команды.
        Один ``Bot`` на два диспетчера не поддерживается: подготовка
        второго затрёт команды первого.

        Args:
            bot: Экземпляр бота.
            rebuild: Признак повторной подготовки после поздних
                регистраций. При нём итог логируется на уровне debug.
        """

        bot.commands.clear()

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

            for error_handler in router.error_handlers:
                error_handler.func_args = frozenset(
                    inspect.signature(error_handler.func_event).parameters,
                )

        self._cached_router_entries = self._build_dispatch_entries()
        self._handlers_dirty = False

        if rebuild:
            logger_dp.debug(
                "Индекс перестроен: %d обработчиков событий", handlers_count
            )
        else:
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

        Используется, когда кеша записей нет
        (``_cached_router_entries is None``): до первой подготовки или
        после инвалидации у диспетчера без ``bot``. Позволяет
        остановить обход дерева роутеров сразу после первого
        совпадения, не аллоцируя полный список. Inner-middleware на
        этом пути могут быть ещё не выпечены в ``handler.mw_chain``
        (это делает :meth:`_prepare_handlers`), поэтому в кортеж
        попадают только ``(router, outer_mw, filters, base_filters)``.
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

        Вызывается на каждой подготовке обработчиков
        (:meth:`_prepare_handlers`); результат сохраняется в
        ``_cached_router_entries`` и используется, пока индекс не
        инвалидирован. Пока кеша нет, работает
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
            Контекст.
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
        event_object: UpdateUnion | dict[str, Any] | str,
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
    async def call_error_handler(
        handler: ErrorHandler,
        event_object: ErrorEventObject,
        data: dict[str, Any],
    ) -> None:
        """
        Вызывает обработчик ошибки с подходящими kwargs.

        Args:
            handler: Обработчик ошибки.
            event_object: Событие ошибки.
            data: Данные, накопленные фильтрами.
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
        event: Any,
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
                О каждом роутере предупреждаем только один раз за всю
                жизнь диспетчера (``_warned_duplicate_routers``): иначе
                каждая перестройка индекса повторяла бы старые
                предупреждения, а дубли, появившиеся уже после старта,
                наоборот, остались бы незамеченными.
        """
        seen: set[int] = set()
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
                    if (
                        warn_duplicates
                        and router not in self._warned_duplicate_routers
                    ):
                        self._warned_duplicate_routers.add(router)
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
        router: Router | Dispatcher | None = None,
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
                router=router,
            ) from e

    async def handle_raw_response(
        self, event_type: UpdateType, raw_data: dict[str, Any] | str
    ) -> None:
        """
        Специальный метод для обработки сырых ответов API.

        ``raw_data`` — разобранный JSON-объект ответа либо сырой текст,
        если тело ответа не является JSON-объектом (например, HTML
        от прокси при 502/503).
        """
        self._ensure_prepared()

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
        router: Router | Dispatcher,
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
                router=router,
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
        router: Router | Dispatcher,
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
        try:
            if await self._run_router_handlers(
                router=router,
                event=event,
                data=handler_data,
                matching_handlers=matching_handlers,
                memory_context=memory_context,
                current_state=current_state,
                router_id=router_id,
                process_info=process_info,
            ):
                handler_data["_handled"] = True
        except HandlerException:
            # Хендлер был найден и запущен — фиксируем флаг до re-raise,
            # чтобы router outer middleware, поглотившая исключение,
            # не получила ложное «Проигнорировано» в handle().
            # Симметрично тому, что делает _process_event для global outer mw.
            handler_data["_handled"] = True
            raise

    async def _dispatch_to_router(
        self,
        router: Router | Dispatcher,
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
            router=router,
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
        # Страховка: между _ensure_prepared() в handle() и этим местом
        # есть await'ы, за которые могла случиться новая регистрация.
        self._ensure_prepared()

        if self._cached_router_entries is not None:
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
                router=router,
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

    def spawn_handle_task(self, event_object: UpdateUnion) -> asyncio.Task:
        """
        Создаёт фоновую задачу ``handle()`` и регистрирует её в пуле.

        Единая точка постановки задач для polling
        (``use_create_task=True``) и webhook-интеграций: без
        регистрации в ``_background_tasks`` задачу может потерять GC,
        а :meth:`shutdown` не дождётся её завершения.

        Args:
            event_object: Событие.

        Returns:
            Созданная задача.
        """
        if self._closing:
            logger_dp.warning(
                "Задача handle() создана во время shutdown: %s",
                event_object.update_type,
            )
        task = asyncio.create_task(self.handle(event_object))
        self._background_tasks.add(task)
        task.add_done_callback(self._on_background_task_done)
        return task

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

        try:
            router_id, is_handled = await self._iter_and_dispatch_routers(
                event_object=event_object,
                data=data,
                memory_context=memory_context,
                current_state=data["_current_state"],
                process_info=data["_process_info"],
            )
        except HandlerException as e:
            # Хендлер был найден и запущен — фиксируем флаги до re-raise,
            # чтобы outer middleware, поглотившая исключение, не получила
            # ложное "Проигнорировано" в handle().
            data["_router_id"] = e.router_id
            data["_is_handled"] = True
            raise

        data["_router_id"] = router_id
        data["_is_handled"] = is_handled

    @staticmethod
    def _unwrap_dispatch_exception(
        exception: BaseException,
    ) -> BaseException:
        """Возвращает исходную ошибку из диспетчерской обёртки."""
        if isinstance(exception, (HandlerException, MiddlewareException)):
            return exception.cause or exception
        return exception

    def _build_error_event(
        self,
        event_object: UpdateUnion,
        exception: BaseException,
        *,
        memory_context: BaseContext,
        current_state: Any | None,
        router_id: Any,
        process_info: str,
    ) -> ErrorEventObject:
        """Создаёт объект события ошибки."""
        return ErrorEventObject(
            update=event_object,
            exception=self._unwrap_dispatch_exception(exception),
            handler_exception=(
                exception if isinstance(exception, HandlerException) else None
            ),
            middleware_exception=(
                exception
                if isinstance(exception, MiddlewareException)
                else None
            ),
            context=memory_context,
            raw_state=current_state,
            router_id=router_id,
            process_info=process_info,
        )

    async def _check_error_handler_match(
        self,
        handler: ErrorHandler,
        event: ErrorEventObject,
        data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Проверяет фильтры обработчика ошибки."""
        if handler.filters and not filter_attrs(event, *handler.filters):
            return None

        if not handler.base_filters:
            return {}

        return await self.process_base_filters(
            event=event, filters=handler.base_filters, data=data
        )

    async def _run_error_handlers(
        self,
        router: Router | Dispatcher,
        event: ErrorEventObject,
        data: dict[str, Any],
    ) -> bool:
        """Запускает первый подходящий обработчик ошибки роутера."""
        for handler in router.error_handlers:
            match_data = await self._check_error_handler_match(
                handler=handler,
                event=event,
                data=data,
            )
            if match_data is None:
                continue

            data.update(match_data)
            await self.call_error_handler(handler, event, data)
            return True

        return False

    async def _process_error(
        self,
        event_object: UpdateUnion,
        exception: BaseException,
        *,
        memory_context: BaseContext,
        current_state: Any | None,
        router_id: Any,
        process_info: str,
    ) -> bool:
        """
        Диспатчит ошибку в ``errors``-обработчики.

        Returns:
            True, если ошибка обработана пользовательским handler.
        """
        error_event = self._build_error_event(
            event_object=event_object,
            exception=exception,
            memory_context=memory_context,
            current_state=current_state,
            router_id=router_id,
            process_info=process_info,
        )
        data: dict[str, Any] = {
            "context": memory_context,
            "raw_state": current_state,
            "router_id": router_id,
            "process_info": process_info,
            "exception": error_event.exception,
            "handler_exception": error_event.handler_exception,
            "middleware_exception": error_event.middleware_exception,
            "update": event_object,
        }

        try:
            router = (
                exception.router
                if isinstance(exception, HandlerException)
                else None
            )
            if (
                router is not None
                and router is not self
                and await self._run_error_handlers(router, error_event, data)
            ):
                return True

            return await self._run_error_handlers(self, error_event, data)
        except Exception as error_handler_exception:
            logger_dp.exception(
                "Ошибка в обработчике ошибки: %r | исходная ошибка: %r",
                error_handler_exception,
                exception,
            )
            return False

    async def handle(self, event_object: UpdateUnion) -> None:
        """
        Основной обработчик события. Применяет фильтры, middleware
        и вызывает нужный handler.

        При включённой изоляции (``event_isolation``) вся обработка —
        от чтения FSM-состояния до завершения хендлера и обработчиков
        ошибок — выполняется под блокировкой по ключу
        ``(chat_id, user_id)``: конкурентные апдейты одного
        пользователя сериализуются.

        Args:
            event_object: Событие.
        """
        process_info = "нет данных"

        # Метка «мы внутри обработчика» видна только текущей задаче:
        # по ней shutdown() распознаёт реентрантный вызов
        # (обработчик остановил диспетчер сам).
        token = _in_handler.set(True)
        try:
            self._ensure_prepared()

            ids = event_object.get_ids()
            process_info = (
                f"{event_object.update_type} | "
                f"chat_id: {ids[0]}, user_id: {ids[1]}"
            )
            async with self.event_isolation.lock(ids):
                await self._handle_locked(
                    event_object=event_object,
                    ids=ids,
                    process_info=process_info,
                )
        except Exception as e:
            logger_dp.exception(
                "Ошибка при обработке события: %s | %r",
                process_info,
                e,
            )
        finally:
            _in_handler.reset(token)

    async def _handle_locked(
        self,
        event_object: UpdateUnion,
        ids: tuple[int | None, int | None],
        process_info: str,
    ) -> None:
        """
        Тело ``handle()``, выполняемое под блокировкой изоляции.

        Args:
            event_object: Событие.
            ids: Ключ ``(chat_id, user_id)``.
            process_info: Строка диагностики для логов.
        """
        router_id = None
        try:
            memory_context = self.__get_context(*ids)
            current_state = await memory_context.get_state()

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
            except HandlerException:
                raise
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

        except HandlerException as e:
            if await self._process_error(
                event_object=event_object,
                exception=e,
                memory_context=memory_context,
                current_state=current_state,
                router_id=e.router_id,
                process_info=process_info,
            ):
                return
            logger_dp.exception(
                "Ошибка в обработчике: %s",
                e,
                exc_info=e.cause,
            )
        except MiddlewareException as e:
            if await self._process_error(
                event_object=event_object,
                exception=e,
                memory_context=memory_context,
                current_state=current_state,
                router_id=e.router_id,
                process_info=process_info,
            ):
                return
            logger_dp.exception(
                "Ошибка при обработке события: router_id: %s | %s | %r",
                e.router_id,
                process_info,
                e,
            )

    async def _sleep_unless_stopped(self, delay: float) -> None:
        """
        Пауза, которую прерывает остановка polling.

        Вне polling (событие остановки не создано) ведёт себя как
        обычный ``asyncio.sleep``.

        Args:
            delay: Длительность паузы в секундах.
        """
        stop_event = self._stop_event

        if stop_event is None:
            await asyncio.sleep(delay)
            return

        with suppress(AsyncioTimeoutError):
            await asyncio.wait_for(stop_event.wait(), delay)

    async def _get_updates_or_stop(self, bot: Bot) -> dict | None:
        """
        Запрашивает обновления, прерываясь на остановке polling.

        Висящий long polling запрос отменяется сразу после
        :meth:`stop_polling`, иначе остановка ждала бы таймаута
        запроса. Вне polling запрос выполняется как обычно.

        Args:
            bot: Экземпляр бота.

        Returns:
            dict | None: ответ API или None, если polling остановлен.
        """
        stop_event = self._stop_event

        if stop_event is None:
            return await bot.get_updates(marker=bot.marker_updates)

        if stop_event.is_set():
            # Остановка уже запрошена — не начинаем новый запрос.
            return None

        fetch = asyncio.ensure_future(
            bot.get_updates(marker=bot.marker_updates)
        )
        waiter = asyncio.ensure_future(stop_event.wait())
        tasks: set[asyncio.Task[Any]] = {fetch, waiter}

        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            # Вспомогательные задачи не должны пережить выход из метода,
            # в том числе при внешней отмене самой задачи polling.
            waiter.cancel()
            if not fetch.done():
                fetch.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        if fetch.cancelled():
            return None

        return fetch.result()

    async def _fetch_updates_once(self, bot: Bot) -> dict | None:
        """
        Делает один запрос get_updates.

        Returns:
            dict | None: словарь событий, или None при
            recoverable-ошибке либо остановке polling.

        Raises:
            InvalidToken: при неверном токене бота.
        """
        try:
            return await self._get_updates_or_stop(bot)
        except AsyncioTimeoutError:
            return None
        except (MaxConnection, ClientConnectorError) as e:
            logger_dp.warning(
                "Ошибка подключения при получении обновлений: %r, "
                "жду %s секунд",
                e,
                CONNECTION_RETRY_DELAY,
            )
            await self._sleep_unless_stopped(CONNECTION_RETRY_DELAY)
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
            await self._sleep_unless_stopped(GET_UPDATES_RETRY_DELAY)
            return None
        except Exception as e:
            logger_dp.error(
                "Неожиданная ошибка при получении обновлений: %r",
                e,
            )
            await self._sleep_unless_stopped(GET_UPDATES_RETRY_DELAY)
            return None

    async def _dispatch_fetched_events(
        self,
        events: dict,
        current_timestamp: int,
        *,
        skip_updates: bool,
    ) -> None:
        """Обрабатывает полученные от API события.

        Маркер сдвигается только после успешной обработки всей пачки:
        если разбор или диспетчеризация упадут, API отдаст те же
        события повторно, и они не потеряются.
        """
        try:
            bot = self._ensure_bot()

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
                    self.spawn_handle_task(event)
                else:
                    await self.handle(event)

            bot.marker_updates = events.get("marker")

        except ClientConnectorError:
            logger_dp.error(
                "Ошибка подключения, жду %s секунд", CONNECTION_RETRY_DELAY
            )
            await self._sleep_unless_stopped(CONNECTION_RETRY_DELAY)
        except Exception as e:
            # Маркер не сдвинут, поэтому та же пачка придёт снова.
            # Пауза нужна, чтобы не крутить цикл вхолостую.
            logger_dp.error(
                "Общая ошибка при обработке событий: %r, жду %s секунд",
                e,
                GET_UPDATES_RETRY_DELAY,
            )
            await self._sleep_unless_stopped(GET_UPDATES_RETRY_DELAY)

    async def start_polling(
        self, bot: Bot, *, skip_updates: bool = False
    ) -> None:
        """
        Запускает цикл получения обновлений (long polling).

        Остановить цикл можно методом :meth:`stop_polling`, который
        дожидается завершения этой задачи.

        Отмена задачи снаружи (``task.cancel()``) корректной остановкой
        не является: цикл прервётся, но фоновые задачи обработчиков
        (``use_create_task=True``) не будут дожданы, а изоляция событий
        не будет закрыта. Останавливайте через :meth:`stop_polling`
        либо вызовите :meth:`shutdown` после отмены. Перед новым
        запуском дождитесь отменённой задачи (``await task`` с
        подавлением ``CancelledError``): пока она не завершилась,
        повторный вызов будет отклонён.

        Ручная остановка через ``dp.polling = False`` (старый идиом)
        оставляет висеть текущий запрос ``get_updates`` до его
        таймаута. Если флаг сброшен снаружи между пачками (после
        получения ответа, но до начала его диспетчеризации), пачка
        целиком пропускается — маркер не сдвинут, и эти события
        придут снова при следующем запуске. А вот сброс флага
        инлайн-обработчиком посреди диспетчеризации самой пачки
        (``use_create_task=False``) на неё уже не влияет: цикл по
        событиям пачки не проверяет ``self.polling`` на каждой
        итерации, поэтому остаток пачки дорабатывается как обычно и
        маркер сдвигается.

        Args:
            bot: Экземпляр бота.
            skip_updates: Флаг, отвечающий за обработку старых событий.

        Raises:
            RuntimeError: Если polling на этом диспетчере уже запущен.
        """
        running = self._polling_task
        if running is not None and not running.done():
            msg = (
                "Polling уже запущен на этом диспетчере. "
                "Остановите его через stop_polling() перед новым "
                "запуском либо используйте отдельный Dispatcher."
            )
            raise RuntimeError(msg)

        self.polling = True
        self._polling_task = asyncio.current_task()
        self._stop_event = asyncio.Event()

        try:
            await self.__ready(bot)

            current_timestamp = to_ms(datetime.now())

            while self.polling:
                events = await self._fetch_updates_once(bot)
                if events is None:
                    # Recoverable-ошибка или остановка: пробуем снова
                    # (или выходим по условию цикла).
                    continue
                if not self.polling:
                    # Пачку, полученную уже после остановки, не
                    # обрабатываем: маркер не сдвинут, и эти события
                    # придут снова при следующем запуске.
                    continue
                await self._dispatch_fetched_events(
                    events, current_timestamp, skip_updates=skip_updates
                )
        finally:
            self.polling = False
            self._polling_task = None
            self._stop_event = None
            # Остановка могла прийтись на подготовку (__ready): та
            # дописывает _ready=True уже после сброса в stop_polling,
            # поэтому сбрасываем здесь — иначе следующий start_polling
            # молча пропустил бы check_me и on_started.
            self._ready = False

            if self._deferred_shutdown:
                # Инлайн-обработчик остановил диспетчер сам: дренаж
                # был отложен, теперь мы вне handle() и можем дождаться
                # фоновых задач и закрыть изоляцию. При внешней отмене
                # задачи (task.cancel()) флаг обычно не выставлен, и
                # лишнего await здесь нет. Но если инлайн-обработчик
                # успел взвести флаг, а затем задачу всё же отменили,
                # отложенный shutdown всё равно выполнится — этот
                # finally отрабатывает и в процессе отмены.
                self._deferred_shutdown = False
                await self.shutdown()

    async def stop_polling(self) -> None:
        """
        Останавливает цикл получения обновлений (long polling).

        Прерывает висящий запрос ``get_updates`` и паузы между
        попытками, после чего дожидается завершения задачи
        :meth:`start_polling` и всех фоновых задач
        (``use_create_task=True``), запущенных до момента остановки.
        После возврата из метода никакой активности диспетчера не
        остаётся.

        Сетевые вызовы этапа старта (``check_me``, проверка подписок) и
        колбэк ``on_started`` не прерываются: остановка дождётся их
        завершения и только потом вернёт управление.

        Если метод вызван из обработчика, выполняющегося прямо в
        задаче polling (``use_create_task=False``), дожидаться её
        нельзя — задача не может дождаться саму себя. В этом случае
        выставляются только флаги, а цикл завершится сразу после
        возврата из обработчика; дренаж фоновых задач и закрытие
        изоляции произойдут сразу после выхода из цикла
        (см. :meth:`shutdown`).

        Ручная остановка через ``dp.polling = False`` полноценной
        заменой не является: висящий запрос ``get_updates`` не
        прерывается, уже полученная пачка не диспетчеризуется (придёт
        снова при следующем запуске), а фоновые задачи и изоляция
        остаются на совести вызывающего.

        Вызов до фактического старта цикла (``create_task`` на
        :meth:`start_polling` без единого await между ними) — no-op:
        задачи ещё нет, флаг ``polling`` не выставлен, и цикл потом
        запустится как обычно. Дайте задаче стартовать (например,
        ``await asyncio.sleep(0)``) перед остановкой.
        """
        if self.polling:
            self.polling = False
            self._ready = False
            if self._stop_event is not None:
                self._stop_event.set()
            logger_dp.info("Останавливаю polling")

        task = self._polling_task
        if (
            task is not None
            and not task.done()
            and task is not asyncio.current_task()
        ):
            await asyncio.wait({task})

            logger_dp.info("Polling остановлен")

            if not task.cancelled() and task.exception() is not None:
                logger_dp.error(
                    "Цикл polling завершился с ошибкой: %r",
                    task.exception(),
                )

        await self.shutdown()

    async def shutdown(self) -> None:
        """
        Завершает работу диспетчера: дожидается фоновых задач
        (``use_create_task=True``) и освобождает ресурсы изоляции
        событий.

        Дожидается в цикле до полного опустошения пула: задача,
        добавленная конкурентным продюсером во время ожидания
        текущего снимка ``_background_tasks``, будет дождана на
        следующей итерации, а не останется вне ожидаемого набора.
        Продюсеры должны быть остановлены до вызова
        (:meth:`stop_polling` сбрасывает ``polling`` заранее;
        webhook-интеграции вызывают shutdown после остановки приёма
        запросов).

        Реентрантный вызов (из обработчика — обычно через
        :meth:`stop_polling`) только выставляет признак завершения:
        дренировать фоновые задачи и закрывать изоляцию нельзя. Другие
        обработчики того же пользователя ждут блокировку
        ``event_isolation``, которую удерживает вызывающий, — ожидание
        их завершения замкнуло бы кольцо. Оставшиеся задачи доработают
        сами; чтобы дождаться их, вызовите ``shutdown()`` снаружи
        обработчика. Исключение — инлайн-обработчик в задаче polling:
        для него дренаж откладывается до выхода из цикла и выполняется
        автоматически (см. :meth:`start_polling`).

        Реентрантным считается вызов из задачи ЭТОГО диспетчера,
        помеченной как выполняющая :meth:`handle`. Кольцо всё же
        возможно, если обработчик сам дожидается порождённой им
        задачи, которая вызывает ``shutdown()``.

        Эвристика опознаёт только задачу самого polling-цикла и
        задачи, поставленные через :meth:`spawn_handle_task`. Если
        ``handle()`` вызван из собственной задачи пользователя
        (``asyncio.create_task`` в обход ``spawn_handle_task``),
        ``shutdown()`` из неё реентрантным не признаётся и пойдёт
        дренировать пул как обычно.

        Отложенный дренаж (см. выше про инлайн-обработчик) выполняется
        только при выходе из цикла polling. Поэтому ``shutdown()`` из
        инлайн-обработчика без последующей остановки polling ничего не
        завершает: флаг ``_deferred_shutdown`` остаётся взведённым до
        конца цикла, а ``_closing=True`` тем временем даёт warning
        в :meth:`spawn_handle_task` при постановке новых задач.

        Готовность (``_ready``) метод не сбрасывает: повторный
        :meth:`startup` подготовку не повторяет (не будет ни
        ``check_me``, ни ``on_started``). Для полного перезапуска
        используйте :meth:`stop_polling`.

        Вызывается автоматически из :meth:`stop_polling` и из
        shutdown-хуков webhook-интеграций
        (:class:`~maxapi.webhook.base.BaseMaxWebhook`). Идемпотентен.
        """
        self._closing = True

        # Метки «мы внутри handle()» мало: ContextVar наследуется в
        # create_task и общий для всех диспетчеров процесса. Реентрантен
        # вызов только из задачи ЭТОГО диспетчера.
        current = asyncio.current_task()
        is_own_task = current is not None and (
            current in self._background_tasks or current is self._polling_task
        )

        if _in_handler.get() and is_own_task:
            if current is self._polling_task:
                # Инлайн-обработчик (use_create_task=False) выполняется
                # в самой задаче polling: дренаж и закрытие изоляции
                # откладываем до выхода из цикла, там мы уже вне
                # handle() (см. finally в start_polling).
                self._deferred_shutdown = True
                logger_dp.debug(
                    "shutdown вызван из инлайн-обработчика: дренаж "
                    "отложен до завершения цикла polling",
                )
            elif others := self._background_tasks - {current}:
                logger_dp.warning(
                    "shutdown вызван из обработчика: дренаж фоновых "
                    "задач (%d) и закрытие изоляции пропущены",
                    len(others),
                )
            else:
                logger_dp.debug(
                    "shutdown вызван из обработчика: дренировать "
                    "нечего, изоляция не закрыта",
                )
            return

        drained = False
        while pending := tuple(self._background_tasks):
            logger_dp.info(
                "Ожидаю завершения %d фоновых задач...",
                len(pending),
            )
            await asyncio.gather(*pending, return_exceptions=True)
            drained = True
        if drained:
            logger_dp.info("Все фоновые задачи завершены")

        await self.event_isolation.close()

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

    @property
    def fsm(self) -> ContextManager:
        """
        Роутер не владеет FSM-хранилищем.
        """
        msg = "Router не владеет FSM-хранилищем. Используйте dp.fsm."
        raise RuntimeError(msg)


class ErrorEventObserver:
    """
    Декоратор для регистрации обработчиков ошибок.
    """

    def __init__(self, router: Dispatcher | Router) -> None:
        """
        Инициализирует декоратор ошибок.

        Args:
            router: Экземпляр роутера или диспетчера.
        """
        self.router = router

    def register(
        self, func_event: Callable, *args: Any, **_kwargs: Any
    ) -> Callable:
        """
        Регистрирует функцию как обработчик ошибки.

        Args:
            func_event: Функция-обработчик ошибки.
            *args: Типы исключений или фильтры.

        Returns:
            Callable: Исходная функция.
        """
        self.router.error_handlers.append(
            ErrorHandler(*args, func_event=func_event)
        )
        # Обработчики ошибок читаются напрямую из router.error_handlers,
        # но инвалидация всё равно нужна: только перестройка заполняет
        # error_handler.func_args (без него call_error_handler на каждой
        # ошибке заново разбирает сигнатуру через inspect).
        self.router._invalidate_handlers()  # noqa: SLF001
        return func_event

    def __call__(self, *args: Any, **kwargs: Any) -> Callable:
        """
        Регистрирует функцию как обработчик ошибки через декоратор.

        Returns:
            Callable: Декоратор.
        """

        def decorator(func_event: Callable) -> Callable:
            return self.register(func_event, *args, **kwargs)

        return decorator


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
            if self.router.bot is not None:
                logger_dp.warning(
                    "Колбэк on_started зарегистрирован после подготовки "
                    "диспетчера: он не будет вызван, подготовка "
                    "диспетчера уже выполнена.",
                )
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
            self.router._invalidate_handlers()  # noqa: SLF001
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
