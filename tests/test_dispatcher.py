"""Тесты для Dispatcher и Router."""

import asyncio
import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest
from maxapi.bot import Bot
from maxapi.context import MemoryContext
from maxapi.dispatcher import Dispatcher, Event, Router
from maxapi.enums.update import UpdateType
from maxapi.filters import F
from maxapi.filters.command import Command, CommandsInfo
from maxapi.filters.handler import Handler
from maxapi.types.updates.bot_started import BotStarted
from maxapi.types.updates.message_created import MessageCreated

logger = logging.getLogger(__name__)


class TestDispatcherInitialization:
    """Тесты инициализации Dispatcher."""

    def test_dispatcher_init_default(self):
        """Тест создания Dispatcher с параметрами по умолчанию."""
        dp = Dispatcher()
        assert dp.router_id is None
        assert dp.use_create_task is False
        assert isinstance(dp.event_handlers, list)
        assert len(dp.event_handlers) == 0
        assert isinstance(dp.contexts, dict)
        assert isinstance(dp.routers, list)
        assert isinstance(dp.outer_middlewares, list)
        assert dp.bot is None
        assert dp.polling is False

    def test_dispatcher_init_with_router_id(self):
        """Тест создания Dispatcher с router_id."""
        dp = Dispatcher(router_id="test_id")
        assert dp.router_id == "test_id"

    def test_dispatcher_init_with_use_create_task(self):
        """Тест создания Dispatcher с use_create_task."""
        dp = Dispatcher(use_create_task=True)
        assert dp.use_create_task is True

    def test_dispatcher_events_initialization(self):
        """Тест инициализации событий в Dispatcher."""
        dp = Dispatcher()
        assert hasattr(dp, "message_created")
        assert hasattr(dp, "bot_started")
        assert hasattr(dp, "message_callback")
        assert isinstance(dp.message_created, Event)
        assert isinstance(dp.bot_started, Event)


class TestRouterInitialization:
    """Тесты инициализации Router."""

    def test_router_init_default(self):
        """Тест создания Router."""
        router = Router()
        assert router.router_id is None
        assert isinstance(router, Dispatcher)

    def test_router_init_with_id(self):
        """Тест создания Router с router_id."""
        router = Router(router_id="test_router")
        assert router.router_id == "test_router"


class TestDispatcherHandlers:
    """Тесты регистрации обработчиков."""

    def test_register_message_created_handler(self, dispatcher):
        """Тест регистрации обработчика message_created."""

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            logger.debug("Получено событие: %s", event)

        assert len(dispatcher.event_handlers) == 1
        handler = dispatcher.event_handlers[0]
        assert handler.update_type == UpdateType.MESSAGE_CREATED

    def test_register_multiple_handlers(self, dispatcher):
        """Тест регистрации нескольких обработчиков."""

        @dispatcher.message_created()
        async def _handler1(event: MessageCreated):
            logger.debug("Получено событие: %s", event)

        @dispatcher.bot_started()
        async def _handler2(event: BotStarted):
            logger.debug("Получено событие: %s", event)

        assert len(dispatcher.event_handlers) == 2

    def test_register_handler_with_filter(self, dispatcher):
        """Тест регистрации обработчика с фильтром."""

        @dispatcher.message_created(F.text == "test")
        async def _handler(event: MessageCreated):
            logger.debug("Получено событие: %s", event)

        assert len(dispatcher.event_handlers) == 1
        handler = dispatcher.event_handlers[0]
        assert handler.filters is not None

    def test_on_started_handler(self, dispatcher):
        """Тест регистрации обработчика on_started."""

        @dispatcher.on_started()
        async def _on_started():
            logger.debug("Бот запущен")

        assert dispatcher.on_started_func is not None


class TestPrepareHandlers:
    @staticmethod
    def make_handler_with_doc(commands, info):
        def func(): ...

        func.__doc__ = f"""
        commands_info: {info}
        """
        return Handler(
            Command(commands),
            func_event=func,
            update_type=UpdateType.ON_STARTED,
        )

    def test_prepare_handlers_assigns_bot_and_extracts_commands(self):
        bot = Bot(token="test")
        dp = Dispatcher()
        router = Router("r1")

        handler = self.make_handler_with_doc("start", "Запустить бота")
        router.event_handlers.append(handler)

        dp.routers.append(router)

        # до подготовки bot ещё не присвоен
        assert router.bot is None
        assert bot.commands == []

        dp._prepare_handlers(bot)

        # после подготовки router должен иметь ссылку на bot
        assert router.bot is bot

        # команды из handler должны быть добавлены в bot.commands
        assert bot.commands == [
            CommandsInfo(commands=["start"], info="Запустить бота")
        ]

    def test_prepare_handlers_multiple_routers_and_handlers(self):
        bot = Bot(token="test")
        dp = Dispatcher()

        r1 = Router("r1")
        r2 = Router("r2")

        h1 = self.make_handler_with_doc("a", "info1")
        h2 = self.make_handler_with_doc(["b", "c"], "info2")

        r1.event_handlers.append(h1)
        r2.event_handlers.append(h2)

        dp.routers.extend([r1, r2])

        dp._prepare_handlers(bot)

        assert r1.bot is bot
        assert r2.bot is bot

        # порядок добавления соответствует обходу роутеров и обработчиков
        assert bot.commands == [
            CommandsInfo(commands=["a"], info="info1"),
            CommandsInfo(commands=["b", "c"], info="info2"),
        ]

    def test_prepare_handlers_with_no_event_handlers_does_nothing(self):
        bot = Bot(token="test")
        dp = Dispatcher()
        router = Router("r1")

        dp.routers.append(router)

        dp._prepare_handlers(bot)

        assert router.bot is bot
        assert bot.commands == []


class TestDispatcherRouters:
    """Тесты работы с роутерами."""

    def test_include_routers(self, dispatcher):
        """Тест добавления роутеров."""
        router1 = Router(router_id="router1")
        router2 = Router(router_id="router2")

        dispatcher.include_routers(router1, router2)

        assert len(dispatcher.routers) == 2
        assert router1 in dispatcher.routers
        assert router2 in dispatcher.routers

    def test_router_handlers(self, dispatcher):
        """Тест обработчиков в роутере."""
        router = Router(router_id="test_router")

        @router.message_created()
        async def _handler(event: MessageCreated):
            logger.debug("Получено событие: %s", event)

        dispatcher.include_routers(router)
        assert len(router.event_handlers) == 1


class TestDispatcherFilters:
    """Тесты фильтров."""

    def test_add_base_filter(self, dispatcher):
        """Тест добавления базового фильтра."""
        # Core Stuff
        from maxapi.filters.filter import BaseFilter

        class TestFilter(BaseFilter):
            async def __call__(self, event):
                logger.debug("Получено событие: %s", event)
                return True

        filter_obj = TestFilter()
        dispatcher.filter(filter_obj)

        assert len(dispatcher.base_filters) == 1
        assert dispatcher.base_filters[0] == filter_obj


class TestDispatcherContext:
    """Тесты работы с контекстом."""

    def test_get_memory_context_new(self, dispatcher):
        """Тест получения нового контекста."""
        context = dispatcher._Dispatcher__get_context(12345, 67890)

        assert isinstance(context, MemoryContext)
        assert context.chat_id == 12345
        assert context.user_id == 67890
        assert len(dispatcher.contexts) == 1

    def test_get_memory_context_existing(self, dispatcher):
        """Тест получения существующего контекста."""
        context1 = dispatcher._Dispatcher__get_context(12345, 67890)
        context2 = dispatcher._Dispatcher__get_context(12345, 67890)

        assert context1 is context2
        assert len(dispatcher.contexts) == 1

    def test_get_memory_context_different_ids(self, dispatcher):
        """Тест получения контекстов для разных ID."""
        context1 = dispatcher._Dispatcher__get_context(12345, 67890)
        context2 = dispatcher._Dispatcher__get_context(54321, 98765)

        assert context1 is not context2
        assert len(dispatcher.contexts) == 2


class TestDispatcherMiddlewareChain:
    """Тесты цепочки middleware."""

    def test_build_middleware_chain(self, dispatcher):
        """Тест построения цепочки middleware."""
        # Core Stuff
        from maxapi.filters.middleware import BaseMiddleware

        call_order = []

        class Middleware1(BaseMiddleware):
            async def __call__(self, handler, event, data):
                call_order.append(1)
                return await handler(event, data)

        class Middleware2(BaseMiddleware):
            async def __call__(self, handler, event, data):
                call_order.append(2)
                return await handler(event, data)

        async def _handler(event, data):
            logger.debug("Получено событие: %s и данные %s", event, data)
            await asyncio.sleep(0)
            call_order.append(3)
            return "result"

        middleware1 = Middleware1()
        middleware2 = Middleware2()

        chain = dispatcher.build_middleware_chain(
            [middleware1, middleware2], _handler
        )

        # Проверяем, что цепочка создана
        # (не вызываем, так как нужен реальный event)
        assert callable(chain)


class TestDispatcherAsync:
    """Асинхронные тесты Dispatcher."""

    async def test_check_me(self, dispatcher, bot):
        """Тест check_me."""
        dispatcher.bot = bot

        with patch.object(
            bot, "get_me", new_callable=AsyncMock
        ) as mock_get_me:
            mock_me = Mock()
            mock_me.username = "test_bot"
            mock_me.first_name = "Test"
            mock_me.user_id = 123
            mock_get_me.return_value = mock_me

            await dispatcher.check_me()

            assert bot.me == mock_me
            mock_get_me.assert_called_once()

    async def test_process_base_filters(
        self, dispatcher, sample_message_created_event
    ):
        """Тест process_base_filters."""
        # Core Stuff
        from maxapi.filters.filter import BaseFilter

        class TestFilter(BaseFilter):
            async def __call__(self, event):
                logger.debug("Получено событие: %s", event)
                return {"test_key": "test_value"}

        filter_obj = TestFilter()
        dispatcher.base_filters.append(filter_obj)

        result = await dispatcher.process_base_filters(
            sample_message_created_event, dispatcher.base_filters
        )

        assert isinstance(result, dict)
        assert result["test_key"] == "test_value"

    async def test_process_base_filters_false(
        self, dispatcher, sample_message_created_event
    ):
        """Тест process_base_filters с возвратом False."""
        # Core Stuff
        from maxapi.filters.filter import BaseFilter

        class TestFilter(BaseFilter):
            async def __call__(self, event):
                logger.debug("Получено событие: %s", event)
                return False

        filter_obj = TestFilter()
        dispatcher.base_filters.append(filter_obj)

        result = await dispatcher.process_base_filters(
            sample_message_created_event, dispatcher.base_filters
        )

        assert result is None


class TestDispatcherSubscriptions:
    async def test_check_subscriptions_no_subscriptions(
        self, dispatcher, bot, caplog
    ):
        """Если подписок нет, предупреждение не логируется."""
        dispatcher.bot = bot
        bot.get_subscriptions = AsyncMock(return_value=Mock(subscriptions=[]))

        caplog.set_level("WARNING")
        await dispatcher._check_subscriptions(bot)

        # Проверяем, что предупреждение с ключевой фразой не встречается
        assert not any(
            (
                record.levelname == "WARNING"
                and "БОТ ИГНОРИРУЕТ POLLING!" in record.getMessage()
            )
            for record in caplog.records
        )

    async def test_check_subscriptions_warns_when_subscriptions(
        self, dispatcher, bot, caplog
    ):
        """Если подписки есть, логируется предупреждение с URL'ами."""
        dispatcher.bot = bot
        subs = [Mock(url="https://a"), Mock(url="https://b")]
        bot.get_subscriptions = AsyncMock(
            return_value=Mock(subscriptions=subs)
        )

        caplog.set_level("WARNING")
        await dispatcher._check_subscriptions(bot)

        warns = [r for r in caplog.records if r.levelname == "WARNING"]
        assert warns, "Ожидалось предупреждение при найденных подписках"

        # Проверяем текст предупреждения и наличие URL'ов
        assert any("БОТ ИГНОРИРУЕТ POLLING!" in r.getMessage() for r in warns)
        joined = ", ".join([s.url for s in subs])
        assert any(joined in r.getMessage() for r in warns)


class TestDispatcherReady:
    async def test_ready_triggers_subscriptions_and_prepare_and_on_started(
        self, dispatcher, bot
    ):
        """Если включён polling и auto_check_subscriptions,
        вызываются проверки подписок, check_me, prepare и on_started.
        """
        dispatcher.polling = True
        bot.auto_check_subscriptions = True

        # Подменяем методы, чтобы отследить вызовы
        dispatcher._check_subscriptions = AsyncMock()
        dispatcher.check_me = AsyncMock()
        dispatcher._prepare_handlers = Mock()
        dispatcher.on_started_func = AsyncMock()

        # Вызов приватного метода __ready
        await dispatcher._Dispatcher__ready(bot)

        # Убедимся, что бот присвоен и бот знает диспетчера
        assert dispatcher.bot is bot
        assert bot.dispatcher is dispatcher

        # Проверяем, что были вызваны ожидаемые методы
        dispatcher._check_subscriptions.assert_called()
        dispatcher.check_me.assert_called()
        dispatcher._prepare_handlers.assert_called_once_with(bot)
        dispatcher.on_started_func.assert_called()

        # Dispatcher должен добавить себя в список роутеров
        assert dispatcher in dispatcher.routers

    async def test_ready_skips_subscriptions_when_polling_disabled(
        self, dispatcher, bot
    ):
        """Если polling отключён, проверка подписок не выполняется."""
        dispatcher.polling = False
        bot.auto_check_subscriptions = True

        dispatcher._check_subscriptions = AsyncMock()
        dispatcher.check_me = AsyncMock()
        dispatcher._prepare_handlers = Mock()
        dispatcher.on_started_func = None

        await dispatcher._Dispatcher__ready(bot)

        # _check_subscriptions не должен вызываться
        dispatcher._check_subscriptions.assert_not_called()

        # Остальные шаги должны выполниться
        dispatcher.check_me.assert_called()
        dispatcher._prepare_handlers.assert_called_once_with(bot)
        assert dispatcher in dispatcher.routers


# ===========================================================================
# Helpers
# ===========================================================================


def _setup_for_handle(dispatcher: Dispatcher, bot: Bot) -> None:
    """Настраивает dispatcher для тестирования полного dispatch-пайплайна."""
    dispatcher.routers.append(dispatcher)
    dispatcher._prepare_handlers(bot)
    dispatcher._global_mw_chain = dispatcher.build_middleware_chain(
        dispatcher.outer_middlewares, dispatcher._process_event
    )


# ===========================================================================
# Полный пайплайн handle → роутеры → обработчик
# ===========================================================================


class TestHandlePipeline:
    """Тесты полного пайплайна dispatch."""

    async def test_handle_dispatches_to_matching_handler(
        self, dispatcher, bot, fixture_message_created
    ):
        """handle() находит и вызывает подходящий обработчик."""
        handled = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            logger.debug("Получено событие: %s", event)
            handled.append(event)

        _setup_for_handle(dispatcher, bot)
        await dispatcher.handle(fixture_message_created)

        assert len(handled) == 1
        assert handled[0] is fixture_message_created

    async def test_handle_no_matching_handler_logs_ignored(
        self, dispatcher, bot, fixture_message_created
    ):
        """
        handle() завершается без ошибки, если нет
        подходящего обработчика.
        """
        _setup_for_handle(dispatcher, bot)
        await dispatcher.handle(fixture_message_created)  # не должно падать

    async def test_handle_uses_cached_router_entries_when_ready(
        self, dispatcher, bot, fixture_message_created
    ):
        """При _ready=True _cached_router_entries строится один раз и
        переиспользуется при повторных вызовах handle()."""
        handled = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            handled.append(event)

        _setup_for_handle(dispatcher, bot)
        dispatcher._ready = True
        # _prepare_handlers уже заполнил кеш; сбрасываем, чтобы
        # покрыть ветку «кеш пуст → построить» внутри handle()
        dispatcher._cached_router_entries = None

        # Первый вызов — строит и кладёт в кеш (строка 1001)
        await dispatcher.handle(fixture_message_created)
        cached = dispatcher._cached_router_entries
        assert cached is not None

        # Второй вызов — использует тот же объект из кеша (строка 1002)
        await dispatcher.handle(fixture_message_created)
        assert dispatcher._cached_router_entries is cached

        assert len(handled) == 2

    async def test_handle_handler_state_mismatch_skips_and_returns_false(
        self, dispatcher, bot, fixture_message_created
    ):
        """Если handler не подходит по state, он пропускается (continue),
        и _run_router_handlers возвращает False."""

        class MyState:
            pass

        required_state = MyState()

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            logger.debug("Получено событие: %s", event)

        # Назначаем состояние, которое не совпадёт (current_state = None)
        dispatcher.event_handlers[-1].states = [required_state]

        _setup_for_handle(dispatcher, bot)
        await dispatcher.handle(fixture_message_created)  # не должно падать

    async def test_handle_catches_handler_exception(
        self, dispatcher, bot, fixture_message_created
    ):
        """handle() перехватывает исключение обработчика и логирует."""

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            raise RuntimeError("ошибка обработчика")

        _setup_for_handle(dispatcher, bot)
        await dispatcher.handle(fixture_message_created)  # не должно всплывать

    async def test_handle_catches_middleware_exception(
        self, dispatcher, bot, fixture_message_created
    ):
        """
        handle() перехватывает MiddlewareException
        из глобального middleware.
        """
        from maxapi.filters.middleware import BaseMiddleware

        class FailingMiddleware(BaseMiddleware):
            async def __call__(self, handler, event, data):
                raise RuntimeError("сбой middleware")

        dispatcher.register_outer_middleware(FailingMiddleware())
        _setup_for_handle(dispatcher, bot)
        await dispatcher.handle(fixture_message_created)  # не должно всплывать


# ===========================================================================
# Вспомогательные методы dispatcher
# ===========================================================================


class TestDispatcherHelpers:
    """Тесты вспомогательных методов Dispatcher."""

    def test_lru_context_move_to_end(self, dispatcher):
        """Повторный доступ к контексту перемещает его в конец (LRU hit)."""
        dispatcher._Dispatcher__get_context(1, 1)
        dispatcher._Dispatcher__get_context(2, 2)

        # Обращаемся к (1,1) — должен переместиться в конец
        dispatcher._Dispatcher__get_context(1, 1)

        keys = list(dispatcher.contexts.keys())
        assert keys[-1] == (1, 1)

    def test_lru_context_evicts_oldest_when_full(self, dispatcher):
        """Когда кеш переполнен, самый старый контекст вытесняется."""
        import maxapi.dispatcher as dp_module

        original = dp_module.CONTEXTS_MAX_SIZE
        dp_module.CONTEXTS_MAX_SIZE = 2
        try:
            dispatcher._Dispatcher__get_context(1, 1)
            dispatcher._Dispatcher__get_context(2, 2)
            # Третий вызов должен вытеснить (1, 1)
            dispatcher._Dispatcher__get_context(3, 3)
            assert (1, 1) not in dispatcher.contexts
            assert len(dispatcher.contexts) == 2
        finally:
            dp_module.CONTEXTS_MAX_SIZE = original

    def test_find_matching_handlers_without_index(self, dispatcher):
        """Fallback на линейный поиск когда handlers_by_type не построен."""
        router = Router(router_id="r1")

        @router.message_created()
        async def _handler(event: MessageCreated):
            logger.debug("Получено событие: %s", event)

        router.handlers_by_type = None  # индекс не построен

        result = dispatcher._find_matching_handlers(
            router, UpdateType.MESSAGE_CREATED
        )
        assert len(result) == 1

    async def test_check_handler_match_state_mismatch(
        self, dispatcher, fixture_message_created
    ):
        """Возвращает None когда текущее состояние не совпадает."""

        class State:
            pass

        state_a, state_b = State(), State()
        handler = Handler(
            func_event=lambda e: None,
            update_type=UpdateType.MESSAGE_CREATED,
        )
        handler.states = [state_a]

        result = await dispatcher._check_handler_match(
            handler=handler,
            event=fixture_message_created,
            current_state=state_b,
        )
        assert result is None

    def test_get_middleware_title_with_func_attr(self, dispatcher):
        """_get_middleware_title берёт имя из chain.func.__class__.__name__."""
        import functools

        from maxapi.filters.middleware import BaseMiddleware

        class MyMiddleware(BaseMiddleware):
            async def __call__(self, handler, event, data):
                return await handler(event, data)

        partial_chain = functools.partial(MyMiddleware(), None)
        title = dispatcher._get_middleware_title(partial_chain)
        assert "MyMiddleware" in title

    def test_get_middleware_title_without_func_attr(self, dispatcher):
        """_get_middleware_title берёт __name__ когда нет .func."""

        async def my_handler(event, data):
            await asyncio.sleep(0)

        title = dispatcher._get_middleware_title(my_handler)
        assert "my_handler" in title


# ===========================================================================
# _execute_handler — обёртка исключения
# ===========================================================================


class TestExecuteHandler:
    async def test_execute_handler_wraps_exception_in_handler_exception(
        self, dispatcher, fixture_message_created
    ):
        """_execute_handler оборачивает RuntimeError в HandlerException."""
        from maxapi.exceptions.dispatcher import HandlerException

        async def _failing(event):
            raise ValueError("тест")

        handler = Handler(
            func_event=_failing,
            update_type=UpdateType.MESSAGE_CREATED,
        )
        handler.func_args = frozenset()
        handler.mw_chain = None

        memory_context = dispatcher._Dispatcher__get_context(1, 2)

        with pytest.raises(HandlerException):
            await dispatcher._execute_handler(
                handler=handler,
                event=fixture_message_created,
                data={},
                handler_middlewares=[],
                memory_context=memory_context,
                current_state=None,
                router_id="test",
                process_info="test",
            )


# ===========================================================================
# stop_polling
# ===========================================================================


class TestStopPolling:
    async def test_stop_polling_sets_polling_false(self, dispatcher):
        dispatcher.polling = True
        await dispatcher.stop_polling()
        assert dispatcher.polling is False

    async def test_stop_polling_already_stopped_no_error(self, dispatcher):
        dispatcher.polling = False
        await dispatcher.stop_polling()  # не должно падать

    async def test_stop_polling_waits_for_background_tasks(self, dispatcher):
        """stop_polling дожидается завершения фоновых задач."""
        completed = []

        async def _work():
            await asyncio.sleep(0)
            completed.append(1)

        dispatcher.polling = True
        task = asyncio.create_task(_work())
        dispatcher._background_tasks.add(task)
        task.add_done_callback(dispatcher._background_tasks.discard)

        await dispatcher.stop_polling()

        assert completed == [1]
        assert len(dispatcher._background_tasks) == 0


# ===========================================================================
# handle_raw_response — перехват исключений
# ===========================================================================


class TestHandleRawResponse:
    async def test_handle_raw_response_catches_handler_exception(
        self, dispatcher, bot
    ):
        """handle_raw_response не всплывает при ошибке обработчика."""
        dispatcher.bot = bot

        async def _failing(event):
            raise RuntimeError("raw error")

        handler = Handler(
            func_event=_failing,
            update_type=UpdateType.RAW_API_RESPONSE,
        )
        dispatcher.event_handlers.append(handler)
        dispatcher.routers.append(dispatcher)
        dispatcher._prepare_handlers(bot)

        await dispatcher.handle_raw_response(
            event_type=UpdateType.RAW_API_RESPONSE,
            raw_data={"test": "data"},
        )


# ===========================================================================
# Handler — BaseFilter как позиционный аргумент
# ===========================================================================


class TestHandlerBaseFilterArg:
    def test_handler_accepts_base_filter_as_positional_arg(self):
        """Handler принимает BaseFilter позиционным аргументом."""
        from maxapi.filters.filter import BaseFilter

        class MyFilter(BaseFilter):
            async def __call__(self, event):
                logger.debug("Получено событие: %s", event)
                return True

        filter_obj = MyFilter()
        handler = Handler(
            filter_obj,
            func_event=lambda e: None,
            update_type=UpdateType.MESSAGE_CREATED,
        )

        assert filter_obj in handler.base_filters

    def test_handler_accepts_base_middleware_as_positional_arg(self):
        """Handler принимает BaseMiddleware позиционным аргументом."""
        from maxapi.filters.middleware import BaseMiddleware

        class MyMiddleware(BaseMiddleware):
            async def __call__(self, handler, event, data):
                return await handler(event, data)

        mw = MyMiddleware()
        handler = Handler(
            mw,
            func_event=lambda e: None,
            update_type=UpdateType.MESSAGE_CREATED,
        )

        assert mw in handler.middlewares


# ===========================================================================
# _fetch_updates_once — ветки обработки ошибок
# ===========================================================================


class TestFetchUpdatesOnce:
    """Тесты всех веток _fetch_updates_once."""

    async def test_returns_updates_on_success(self, dispatcher, bot):
        dispatcher.bot = bot
        bot.get_updates = AsyncMock(return_value={"updates": [], "marker": 1})
        result = await dispatcher._fetch_updates_once(bot)
        assert result == {"updates": [], "marker": 1}

    async def test_asyncio_timeout_returns_none(self, dispatcher, bot):
        from asyncio.exceptions import TimeoutError as AsyncioTimeoutError

        bot.get_updates = AsyncMock(side_effect=AsyncioTimeoutError())
        result = await dispatcher._fetch_updates_once(bot)
        assert result is None

    async def test_max_connection_error_returns_none(self, dispatcher, bot):
        from maxapi.exceptions.max import MaxConnection

        bot.get_updates = AsyncMock(side_effect=MaxConnection("conn error"))
        with patch("maxapi.dispatcher.CONNECTION_RETRY_DELAY", 0):
            result = await dispatcher._fetch_updates_once(bot)
        assert result is None

    async def test_invalid_token_stops_polling(self, dispatcher, bot):
        from maxapi.exceptions.max import InvalidToken

        bot.get_updates = AsyncMock(side_effect=InvalidToken("bad token"))
        dispatcher.polling = True
        with pytest.raises(InvalidToken):
            await dispatcher._fetch_updates_once(bot)
        assert dispatcher.polling is False

    async def test_max_api_error_returns_none(self, dispatcher, bot):
        from maxapi.exceptions.max import MaxApiError

        bot.get_updates = AsyncMock(side_effect=MaxApiError(400, "api error"))
        with patch("maxapi.dispatcher.GET_UPDATES_RETRY_DELAY", 0):
            result = await dispatcher._fetch_updates_once(bot)
        assert result is None

    async def test_generic_exception_returns_none(self, dispatcher, bot):
        bot.get_updates = AsyncMock(side_effect=RuntimeError("unexpected"))
        with patch("maxapi.dispatcher.GET_UPDATES_RETRY_DELAY", 0):
            result = await dispatcher._fetch_updates_once(bot)
        assert result is None


# ===========================================================================
# _dispatch_fetched_events — обработка полученных событий
# ===========================================================================


class TestDispatchFetchedEvents:
    """Тесты _dispatch_fetched_events."""

    async def test_dispatches_events_sequentially(
        self, dispatcher, bot, fixture_message_created
    ):
        """События обрабатываются последовательно (use_create_task=False)."""
        handled = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            logger.debug("Получено событие: %s", event)
            handled.append(event)

        dispatcher.bot = bot
        _setup_for_handle(dispatcher, bot)

        raw = {"updates": [fixture_message_created.model_dump()], "marker": 1}

        with patch(
            "maxapi.dispatcher.process_update_request",
            new=AsyncMock(return_value=[fixture_message_created]),
        ):
            await dispatcher._dispatch_fetched_events(
                events=raw,
                current_timestamp=0,
                skip_updates=False,
            )

        assert len(handled) == 1

    async def test_skips_old_events_when_skip_updates_true(
        self, dispatcher, bot, fixture_message_created
    ):
        """Старые события пропускаются при skip_updates=True."""
        handled = []

        @dispatcher.message_created()
        async def _handler(event: MessageCreated):
            logger.debug("Получено событие: %s", event)
            handled.append(event)

        dispatcher.bot = bot
        _setup_for_handle(dispatcher, bot)

        # timestamp события меньше current_timestamp → пропуск
        future_timestamp = fixture_message_created.timestamp + 1_000_000_000

        with patch(
            "maxapi.dispatcher.process_update_request",
            new=AsyncMock(return_value=[fixture_message_created]),
        ):
            await dispatcher._dispatch_fetched_events(
                events={},
                current_timestamp=future_timestamp,
                skip_updates=True,
            )

        assert len(handled) == 0

    async def test_use_create_task_creates_background_task(
        self, dispatcher, bot, fixture_message_created
    ):
        """
        При use_create_task=True событие обрабатывается
        через asyncio.Task.
        """
        dispatcher.use_create_task = True
        dispatcher.bot = bot
        _setup_for_handle(dispatcher, bot)

        with patch(
            "maxapi.dispatcher.process_update_request",
            new=AsyncMock(return_value=[fixture_message_created]),
        ):
            await dispatcher._dispatch_fetched_events(
                events={},
                current_timestamp=0,
                skip_updates=False,
            )
            # Даём задаче и её done-callback завершиться
            for _ in range(3):
                await asyncio.sleep(0)

        assert len(dispatcher._background_tasks) == 0  # задача завершена


# ===========================================================================
# call_handler — **data передаётся хендлеру
# ===========================================================================


class TestCallHandlerWithKwargs:
    """Хендлер получает kwargs, возвращённые BaseFilter."""

    async def test_handler_receives_kwargs_from_base_filter(
        self, dispatcher, bot, fixture_message_created
    ):
        """BaseFilter возвращает dict → handler получает kwargs."""
        from maxapi.filters.filter import BaseFilter

        received: dict = {}

        class DataFilter(BaseFilter):
            async def __call__(self, event):
                return {"answer": 42}

        @dispatcher.message_created(DataFilter())
        async def _h(event: MessageCreated, answer: int):
            received["answer"] = answer

        _setup_for_handle(dispatcher, bot)
        await dispatcher.handle(fixture_message_created)

        assert received.get("answer") == 42


# ===========================================================================
# _iter_routers — вложенные роутеры и защита от циклов
# ===========================================================================


class TestIterRoutersNested:
    """Рекурсивный обход sub-роутеров доходит до вложенных обработчиков."""

    async def test_nested_sub_router_handler_is_dispatched(
        self, dispatcher, bot, fixture_message_created
    ):
        """Обработчик во вложенном sub-роутере вызывается."""
        handled = []

        nested = Router(router_id="sub_nested")

        @nested.message_created()
        async def _h(event: MessageCreated):
            handled.append(event)

        outer = Router(router_id="sub_outer")
        outer.include_routers(nested)
        dispatcher.include_routers(outer)

        _setup_for_handle(dispatcher, bot)
        await dispatcher.handle(fixture_message_created)

        assert len(handled) == 1


class TestIterRoutersCycle:
    """Цикл в графе роутеров обрабатывается без зависания."""

    def test_cycle_detection_does_not_hang(self, dispatcher):
        r_a = Router(router_id="cycle_a")
        r_b = Router(router_id="cycle_b")
        r_a.include_routers(r_b)
        r_b.include_routers(r_a)  # цикл

        dispatcher.include_routers(r_a)

        result = list(dispatcher._iter_unique_routers(dispatcher.routers))
        ids = {r.router_id for r, *_ in result}
        assert "cycle_a" in ids
        assert "cycle_b" in ids


# ===========================================================================
# _iter_unique_routers — предупреждение о дублях
# ===========================================================================


class TestDuplicateRouterWarning:
    """Повторное включение одного и того же роутера логирует предупреждение."""

    def test_warns_on_duplicate_inclusion(self, dispatcher, caplog):
        router = Router(router_id="dup_router")
        dispatcher.include_routers(router)
        dispatcher.include_routers(router)  # дубль

        with caplog.at_level("WARNING", logger="maxapi.dispatcher"):
            list(
                dispatcher._iter_unique_routers(
                    dispatcher.routers, warn_duplicates=True
                )
            )

        assert any("dup_router" in r.getMessage() for r in caplog.records)


# ===========================================================================
# Фильтры на уровне роутера
# ===========================================================================


class TestRouterLevelFilters:
    async def test_failing_magic_filter_skips_router(
        self, dispatcher, bot, fixture_message_created
    ):
        """Неподходящий MagicFilter на роутере пропускает весь роутер."""
        handled = []

        router = Router(router_id="filtered_router")
        router.filters.append(F.text == "__NEVER_MATCH__")

        @router.message_created()
        async def _h(event: MessageCreated):
            handled.append(event)

        dispatcher.include_routers(router)
        _setup_for_handle(dispatcher, bot)

        await dispatcher.handle(fixture_message_created)

        assert len(handled) == 0

    async def test_router_base_filter_calls_process_base_filters(
        self, dispatcher, bot, fixture_message_created
    ):
        """BaseFilter на роутере вызывается и передаёт данные в обработчик."""
        from maxapi.filters.filter import BaseFilter

        enriched: dict = {}

        class RouterBaseFilter(BaseFilter):
            async def __call__(self, event):
                return {"router_key": "router_val"}

        router = Router(router_id="base_filter_router")
        router.base_filters.append(RouterBaseFilter())

        @router.message_created()
        async def _h(event: MessageCreated, router_key: str = ""):
            enriched["router_key"] = router_key

        dispatcher.include_routers(router)
        _setup_for_handle(dispatcher, bot)

        await dispatcher.handle(fixture_message_created)

        assert enriched.get("router_key") == "router_val"


# ===========================================================================
# Middleware на уровне роутера
# ===========================================================================


class TestRouterMiddlewareChain:
    """Middleware, добавленный на роутер, оборачивает его обработчики."""

    async def test_router_middleware_wraps_dispatch(
        self, dispatcher, bot, fixture_message_created
    ):
        from maxapi.filters.middleware import BaseMiddleware

        calls: list = []

        class RouterMW(BaseMiddleware):
            async def __call__(self, handler, event, data):
                calls.append("mw")
                return await handler(event, data)

        router = Router(router_id="mw_router")
        router.register_outer_middleware(RouterMW())

        @router.message_created()
        async def _h(event: MessageCreated):
            calls.append("handler")

        dispatcher.include_routers(router)
        _setup_for_handle(dispatcher, bot)

        await dispatcher.handle(fixture_message_created)

        assert "mw" in calls
        assert "handler" in calls


# ===========================================================================
# ClientConnectorError в _dispatch_fetched_events
# ===========================================================================


class TestDispatchFetchedEventsConnectorError:
    """_dispatch_fetched_events перехватывает сетевые и прочие исключения."""

    async def test_client_connector_error_caught_and_logged(
        self, dispatcher, bot
    ):
        from unittest.mock import Mock

        from aiohttp import ClientConnectorError

        dispatcher.bot = bot
        _setup_for_handle(dispatcher, bot)

        err = ClientConnectorError(Mock(), ConnectionRefusedError("refused"))

        with (
            patch(
                "maxapi.dispatcher.process_update_request",
                new=AsyncMock(side_effect=err),
            ),
            patch("maxapi.dispatcher.CONNECTION_RETRY_DELAY", 0),
        ):
            await dispatcher._dispatch_fetched_events(
                events={"updates": [], "marker": 0},
                current_timestamp=0,
                skip_updates=False,
            )  # не должно всплывать

    async def test_generic_exception_caught_and_logged(self, dispatcher, bot):
        """Произвольное исключение в _dispatch_fetched_events не всплывает."""
        dispatcher.bot = bot
        _setup_for_handle(dispatcher, bot)

        with patch(
            "maxapi.dispatcher.process_update_request",
            new=AsyncMock(
                side_effect=RuntimeError("unexpected dispatch error")
            ),
        ):
            await dispatcher._dispatch_fetched_events(
                events={"updates": [], "marker": 0},
                current_timestamp=0,
                skip_updates=False,
            )  # не должно всплывать


# ===========================================================================
# start_polling — полный HTTP-цикл через aresponses
# ===========================================================================


class TestStartPollingWithAresponses:
    """
    Интеграционный тест start_polling через сетевую эмуляцию (aresponses).

    aresponses перехватывает TCP-соединения на уровне резолвера и
    перенаправляет их на локальный mock-сервер — никакого реального
    подключения к platform-api.max.ru не происходит.
    """

    async def test_start_polling_calls_http_endpoints_and_stops(
        self, aresponses
    ):
        """
        Проверяет, что start_polling:
          1. обращается к /me (check_me)
          2. первый /updates возвращает 500 → _fetch_updates_once → None
          3. второй /updates возвращает {} → _dispatch_fetched_events вызван
        """
        from aiohttp import web
        from maxapi.bot import Bot
        from maxapi.client.default import DefaultConnectionProperties

        bot = Bot(
            token="polling_test_token",
            auto_check_subscriptions=False,
            default_connection=DefaultConnectionProperties(
                max_retries=0, timeout=5, sock_connect=5
            ),
        )
        dp = Dispatcher()

        # ── Mock GET /me ──────────────────────────────────────────────────
        aresponses.add(
            "platform-api.max.ru",
            "/me",
            "get",
            {
                "user_id": 42,
                "first_name": "PollingBot",
                "is_bot": True,
                "last_activity_time": 1_700_000_000,
            },
        )

        # ── Mock GET /updates (1st): 500 → MaxApiError → returns None ────
        aresponses.add(
            "platform-api.max.ru",
            "/updates",
            "get",
            web.Response(
                status=500,
                text='{"code":500,"message":"test_error"}',
                content_type="application/json",
            ),
        )

        # ── Mock GET /updates (2nd): 200 → events dict → dispatch ────────
        aresponses.add(
            "platform-api.max.ru",
            "/updates",
            "get",
            {"updates": [], "marker": 0},
        )

        # После первого же вызова _dispatch_fetched_events останавливаем цикл
        async def _stop(events, ts, *, skip_updates):
            dp.polling = False

        dp._dispatch_fetched_events = _stop

        with patch("maxapi.dispatcher.GET_UPDATES_RETRY_DELAY", 0):
            await dp.start_polling(bot)

        assert bot.me is not None
        assert bot.me.user_id == 42

        if bot.session and not bot.session.closed:
            await bot.session.close()


# ===========================================================================
# startup
# ===========================================================================


class TestStartup:
    """startup() привязывает бота и подготавливает обработчики."""

    async def test_startup_calls_ready(self, dispatcher, bot):
        dispatcher.check_me = AsyncMock()
        dispatcher._prepare_handlers = Mock()

        await dispatcher.startup(bot)

        assert dispatcher.bot is bot
        assert bot.dispatcher is dispatcher
        dispatcher.check_me.assert_called_once()
        dispatcher._prepare_handlers.assert_called_once_with(bot)


# ===========================================================================
# handle_webhook
# ===========================================================================


class TestHandleWebhook:
    """handle_webhook() создаёт экземпляр webhook-класса и запускает его."""

    async def test_handle_webhook_creates_and_runs_instance(
        self, dispatcher, bot
    ):
        mock_wh_instance = Mock()
        mock_wh_instance.run = AsyncMock()
        mock_wh_type = Mock(return_value=mock_wh_instance)

        await dispatcher.handle_webhook(
            bot,
            host="localhost",
            port=8080,
            path="/hook",
            webhook_type=mock_wh_type,
        )

        mock_wh_type.assert_called_once_with(
            dp=dispatcher, bot=bot, secret=None
        )
        mock_wh_instance.run.assert_called_once_with(
            host="localhost", port=8080, path="/hook"
        )


# ===========================================================================
# Устаревшее событие — DeprecationWarning
# ===========================================================================


class TestDeprecatedEvent:
    """Регистрация на устаревшее событие вызывает DeprecationWarning."""

    def test_deprecated_event_emits_deprecation_warning(self):
        import warnings

        dp = Dispatcher()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            @dp.message_chat_created()
            async def _h(event):
                pass

        assert any(issubclass(x.category, DeprecationWarning) for x in w)


# ===========================================================================
# _on_background_task_done — ветка с исключением в задаче
# ===========================================================================


class TestOnBackgroundTaskDone:
    """_on_background_task_done логирует исключение упавшей задачи."""

    async def test_logs_exception_when_task_has_exception(self, dispatcher):
        """Callback логирует исключение, если задача завершилась с ошибкой."""

        async def _failing():
            raise RuntimeError("test error from background task")

        task = asyncio.create_task(_failing())
        dispatcher._background_tasks.add(task)
        # Ждём завершения, подавляя исключение
        await asyncio.gather(task, return_exceptions=True)

        with patch("maxapi.dispatcher.logger_dp") as mock_logger:
            dispatcher._on_background_task_done(task)
            mock_logger.exception.assert_called_once()
