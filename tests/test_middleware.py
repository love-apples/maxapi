"""Тесты outer и inner middleware на Dispatcher и Router.

Проверяет:
- register_outer_middleware: добавляет в outer_middlewares, порядок append
- register_inner_middleware: добавляет в inner_middlewares, порядок append
- outer_mw срабатывает всегда (до проверки handler-фильтров)
- inner_mw срабатывает только когда handler реально совпал
- deprecated aliases: .middlewares, .middleware(), .outer_middleware()
- наследование outer_mw и inner_mw через дерево роутеров
"""

import warnings

from maxapi.dispatcher import Dispatcher, Router
from maxapi.filters.filter import BaseFilter
from maxapi.filters.middleware import BaseMiddleware
from maxapi.types.updates.bot_started import BotStarted
from maxapi.types.updates.message_created import MessageCreated

# ---------------------------------------------------------------------------
# Вспомогательные классы
# ---------------------------------------------------------------------------


class TrackingMW(BaseMiddleware):
    """Middleware, пишущий вызовы в лог."""

    def __init__(self, name: str, log: list) -> None:
        self.name = name
        self.log = log

    async def __call__(self, handler, event, data) -> None:
        self.log.append(f"{self.name}:before")
        await handler(event, data)
        self.log.append(f"{self.name}:after")


class BlockFilter(BaseFilter):
    """BaseFilter, всегда блокирующий событие."""

    async def __call__(self, event) -> bool:
        return False


def _setup(dp: Dispatcher, bot) -> None:
    """Стандартная инициализация dp для тестов пайплайна."""
    dp.routers.append(dp)
    dp._prepare_handlers(bot)
    dp._global_mw_chain = dp.build_middleware_chain(
        dp.outer_middlewares, dp._process_event
    )


# ===========================================================================
# Регистрация: outer
# ===========================================================================


class TestRegisterOuterMiddleware:
    """register_outer_middleware регистрирует в outer_middlewares."""

    def test_single(self):
        """Одна регистрация — один элемент, inner не затронут."""
        dp = Dispatcher()
        mw = TrackingMW("o", [])
        dp.register_outer_middleware(mw)
        assert dp.outer_middlewares == [mw]
        assert dp.inner_middlewares == []

    def test_append_order(self):
        """Каждая регистрация добавляет mw в конец (append).

        Симметрично с register_inner_middleware: первый
        зарегистрированный mw — самый внешний слой цепочки.
        """
        dp = Dispatcher()
        mw1 = TrackingMW("o1", [])
        mw2 = TrackingMW("o2", [])
        dp.register_outer_middleware(mw1)
        dp.register_outer_middleware(mw2)
        assert dp.outer_middlewares[0] is mw1
        assert dp.outer_middlewares[1] is mw2

    def test_router_outer_middleware(self):
        """Router.register_outer_middleware пишет в outer_middlewares."""
        router = Router()
        mw = TrackingMW("ro", [])
        router.register_outer_middleware(mw)
        assert router.outer_middlewares == [mw]
        assert router.inner_middlewares == []


# ===========================================================================
# Регистрация: inner
# ===========================================================================


class TestRegisterInnerMiddleware:
    """register_inner_middleware регистрирует в inner_middlewares."""

    def test_single(self):
        """Одна регистрация — один элемент, outer не затронут."""
        dp = Dispatcher()
        mw = TrackingMW("i", [])
        dp.register_inner_middleware(mw)
        assert dp.inner_middlewares == [mw]
        assert dp.outer_middlewares == []

    def test_append_order(self):
        """Каждая регистрация добавляет mw в конец (append)."""
        dp = Dispatcher()
        mw1 = TrackingMW("i1", [])
        mw2 = TrackingMW("i2", [])
        dp.register_inner_middleware(mw1)
        dp.register_inner_middleware(mw2)
        assert dp.inner_middlewares[0] is mw1
        assert dp.inner_middlewares[1] is mw2

    def test_router_inner_middleware(self):
        """Router.register_inner_middleware пишет в inner_middlewares."""
        router = Router()
        mw = TrackingMW("ri", [])
        router.register_inner_middleware(mw)
        assert router.inner_middlewares == [mw]
        assert router.outer_middlewares == []


# ===========================================================================
# Deprecated aliases
# ===========================================================================


class TestDeprecatedMiddlewareAliases:
    """Устаревшие методы и свойство .middlewares выдают DeprecationWarning."""

    def test_middlewares_property_warns(self):
        """dp.middlewares возвращает outer_middlewares с предупреждением."""
        dp = Dispatcher()
        mw = TrackingMW("x", [])
        dp.outer_middlewares.append(mw)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            lst = dp.middlewares

        assert any(issubclass(x.category, DeprecationWarning) for x in w)
        assert lst is dp.outer_middlewares
        assert lst == [mw]

    def test_middleware_method_warns_and_appends(self):
        """dp.middleware(mw) добавляет в outer_middlewares с Warning."""
        dp = Dispatcher()
        mw = TrackingMW("x", [])

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            dp.middleware(mw)

        assert any(issubclass(x.category, DeprecationWarning) for x in w)
        assert mw in dp.outer_middlewares

    def test_outer_middleware_method_warns_and_inserts(self):
        """dp.outer_middleware(mw) вставляет в начало outer_middlewares."""
        dp = Dispatcher()
        mw1 = TrackingMW("y1", [])
        mw2 = TrackingMW("y2", [])
        dp.outer_middlewares.append(mw1)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            dp.outer_middleware(mw2)

        assert any(issubclass(x.category, DeprecationWarning) for x in w)
        assert dp.outer_middlewares[0] is mw2
        assert dp.outer_middlewares[1] is mw1

    def test_middlewares_property_returns_list_by_reference(self):
        """Мутация через dp.middlewares.append меняет outer_middlewares."""
        dp = Dispatcher()
        mw = TrackingMW("z", [])

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            dp.middlewares.append(mw)

        assert mw in dp.outer_middlewares


# ===========================================================================
# Поведение outer_mw при dispatch
# ===========================================================================


class TestOuterMiddlewareBehavior:
    """outer_mw вызывается до проверки handler-фильтров."""

    async def test_outer_mw_called_when_handler_matches(
        self, bot, fixture_message_created
    ):
        """outer_mw вызывается при совпадении handler."""
        dp = Dispatcher()
        log: list[str] = []
        dp.register_outer_middleware(TrackingMW("outer", log))

        @dp.message_created()
        async def _h(event: MessageCreated):
            log.append("handler")

        _setup(dp, bot)
        await dp.handle(fixture_message_created)

        assert "outer:before" in log
        assert log.index("outer:before") < log.index("handler")

    async def test_outer_mw_called_even_when_filter_rejects(
        self, bot, fixture_message_created
    ):
        """outer_mw вызывается, даже если handler-фильтр не пройден."""
        dp = Dispatcher()
        log: list[str] = []
        dp.register_outer_middleware(TrackingMW("outer", log))

        @dp.message_created(BlockFilter())
        async def _h(event: MessageCreated):
            log.append("handler")

        _setup(dp, bot)
        await dp.handle(fixture_message_created)

        assert "outer:before" in log
        assert "handler" not in log

    async def test_outer_mw_wraps_handler_post_call(
        self, bot, fixture_message_created
    ):
        """outer_mw выполняет код и после handler (оборачивает целиком)."""
        dp = Dispatcher()
        log: list[str] = []
        dp.register_outer_middleware(TrackingMW("outer", log))

        @dp.message_created()
        async def _h(event: MessageCreated):
            log.append("handler")

        _setup(dp, bot)
        await dp.handle(fixture_message_created)

        assert log == ["outer:before", "handler", "outer:after"]


# ===========================================================================
# Поведение inner_mw при dispatch
# ===========================================================================


class TestInnerMiddlewareBehavior:
    """inner_mw вызывается только при реальном совпадении handler."""

    async def test_inner_mw_called_when_handler_matches(
        self, bot, fixture_message_created
    ):
        """inner_mw вызывается, если handler подходит."""
        dp = Dispatcher()
        log: list[str] = []
        dp.register_inner_middleware(TrackingMW("inner", log))

        handled = []

        @dp.message_created()
        async def _h(event: MessageCreated):
            handled.append(event)
            log.append("handler")

        _setup(dp, bot)
        await dp.handle(fixture_message_created)

        assert handled, "handler должен был вызваться"
        assert "inner:before" in log
        assert "inner:after" in log
        assert log.index("inner:before") < log.index("handler")

    async def test_inner_mw_not_called_when_no_handler_matches(
        self, bot, fixture_message_created
    ):
        """inner_mw НЕ вызывается, если ни один handler не подошёл."""
        dp = Dispatcher()
        log: list[str] = []
        dp.register_inner_middleware(TrackingMW("inner", log))

        @dp.bot_started()
        async def _h(event: BotStarted):
            log.append("handler")

        _setup(dp, bot)
        await dp.handle(fixture_message_created)

        assert "inner:before" not in log
        assert "inner:after" not in log
        assert "handler" not in log

    async def test_inner_mw_not_called_when_filter_rejects(
        self, bot, fixture_message_created
    ):
        """inner_mw НЕ вызывается, если handler-фильтр блокирует событие."""
        dp = Dispatcher()
        log: list[str] = []
        dp.register_inner_middleware(TrackingMW("inner", log))

        @dp.message_created(BlockFilter())
        async def _h(event: MessageCreated):
            log.append("handler")

        _setup(dp, bot)
        await dp.handle(fixture_message_created)

        assert "inner:before" not in log
        assert "handler" not in log

    async def test_inner_and_outer_both_called_on_match(
        self, bot, fixture_message_created
    ):
        """outer и inner вызываются в правильном порядке при совпадении."""
        dp = Dispatcher()
        log: list[str] = []
        dp.register_outer_middleware(TrackingMW("outer", log))
        dp.register_inner_middleware(TrackingMW("inner", log))

        @dp.message_created()
        async def _h(event: MessageCreated):
            log.append("handler")

        _setup(dp, bot)
        await dp.handle(fixture_message_created)

        assert "outer:before" in log
        assert "inner:before" in log
        assert "handler" in log
        assert log.index("outer:before") < log.index("inner:before")
        assert log.index("inner:before") < log.index("handler")


# ===========================================================================
# Наследование через дерево роутеров
# ===========================================================================


class TestOuterMiddlewareInheritance:
    """outer_mw наследуется дочерними роутерами."""

    def test_iter_routers_accumulates_outer_mw(self):
        """_iter_routers накапливает outer_mw по дереву."""
        dp = Dispatcher()
        parent = Router("parent")
        child = Router("child")

        mw_p = TrackingMW("p", [])
        mw_c = TrackingMW("c", [])
        parent.register_outer_middleware(mw_p)
        child.register_outer_middleware(mw_c)
        parent.include_routers(child)
        dp.include_routers(parent)

        results = {r: omw for r, omw, *_ in dp._iter_routers(dp.routers)}
        assert results[parent] == [mw_p]
        assert results[child] == [mw_p, mw_c]

    async def test_router_outer_mw_wraps_child_handler(
        self, bot, fixture_message_created
    ):
        """outer_mw родителя оборачивает handler из дочернего роутера."""
        dp = Dispatcher()
        parent = Router("parent")
        child = Router("child")
        log: list[str] = []

        parent.register_outer_middleware(TrackingMW("parent_outer", log))

        @child.message_created()
        async def _h(event: MessageCreated):
            log.append("handler")

        parent.include_routers(child)
        dp.include_routers(parent)
        _setup(dp, bot)
        await dp.handle(fixture_message_created)

        assert log == ["parent_outer:before", "handler", "parent_outer:after"]


class TestInnerMiddlewareInheritance:
    """inner_mw наследуется дочерними роутерами."""

    async def test_child_router_inherits_parent_inner_mw(
        self, bot, fixture_message_created
    ):
        """handler в child-роутере получает parent и child inner_mw."""
        dp = Dispatcher()
        parent = Router("parent")
        child = Router("child")

        log: list[str] = []
        parent.register_inner_middleware(TrackingMW("p_inner", log))
        child.register_inner_middleware(TrackingMW("c_inner", log))

        parent.include_routers(child)
        dp.include_routers(parent)

        handled = []

        @child.message_created()
        async def _h(event: MessageCreated):
            handled.append(event)
            log.append("handler")

        _setup(dp, bot)
        await dp.handle(fixture_message_created)

        assert handled, "handler должен вызваться"
        assert "p_inner:before" in log
        assert "c_inner:before" in log
        assert log.index("p_inner:before") < log.index("c_inner:before")

    def test_iter_routers_accumulates_inner_mw(self):
        """_iter_routers накапливает inner_mw по дереву."""
        dp = Dispatcher()
        parent = Router("parent")
        child = Router("child")

        mw_p = TrackingMW("p", [])
        mw_c = TrackingMW("c", [])
        parent.register_inner_middleware(mw_p)
        child.register_inner_middleware(mw_c)
        parent.include_routers(child)
        dp.include_routers(parent)

        results = {r: imw for r, omw, imw, *_ in dp._iter_routers(dp.routers)}
        assert results[parent] == [mw_p]
        assert results[child] == [mw_p, mw_c]

    async def test_dp_inner_mw_applied_to_all_routers(
        self, bot, fixture_message_created
    ):
        """Глобальный dp.inner_mw применяется к handler в любом роутере."""
        dp = Dispatcher()
        router = Router("router")
        dp.include_routers(router)

        log: list[str] = []
        dp.register_inner_middleware(TrackingMW("global_inner", log))

        handled = []

        @router.message_created()
        async def _h(event: MessageCreated):
            handled.append(event)
            log.append("handler")

        _setup(dp, bot)
        await dp.handle(fixture_message_created)

        assert handled
        assert "global_inner:before" in log
