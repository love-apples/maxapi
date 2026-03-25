"""Тесты вложенных роутеров — наследование middleware, фильтров и BaseFilter."""

import pytest

from maxapi.dispatcher import Dispatcher, Router
from maxapi.filters.filter import BaseFilter
from maxapi.filters.middleware import BaseMiddleware


class TrackingMiddleware(BaseMiddleware):
    """
    Middleware, записывающий порядок вызовов в переданный лог.
    """

    def __init__(self, name: str, log: list) -> None:
        self.name = name
        self.log = log

    async def __call__(self, handler, event, data) -> None:
        self.log.append(f"{self.name}:before")
        await handler(event, data)
        self.log.append(f"{self.name}:after")


class BlockingMiddleware(BaseMiddleware):
    """
    Middleware, не передающий управление дальше по цепочке.
    """

    def __init__(self, log: list) -> None:
        self.log = log

    async def __call__(self, handler, event, data) -> None:
        self.log.append("blocked")


class AllowFilter(BaseFilter):
    """BaseFilter, всегда пропускающий событие."""

    async def __call__(self, event) -> bool:
        return True


class BlockFilter(BaseFilter):
    """BaseFilter, всегда блокирующий событие."""

    async def __call__(self, event) -> bool:
        return False


class DataFilter(BaseFilter):
    """BaseFilter, добавляющий данные в контекст хендлера."""

    def __init__(self, key: str, value) -> None:
        self.key = key
        self.value = value

    async def __call__(self, event) -> dict:
        return {self.key: self.value}


class TestIterRouters:
    """
    Unit-тесты метода _iter_routers.

    Проверяет накопление middleware, filters и base_filters
    при обходе дерева роутеров.
    """

    def test_single_router_yields_own_middlewares(self):
        """Один роутер без родителей отдаёт только свои middleware."""
        dp = Dispatcher()
        router = Router("r")
        mw = TrackingMiddleware("mw", [])
        router.middleware(mw)
        dp.include_routers(router)

        results = {r: mws for r, mws, *_ in dp._iter_routers(dp.routers)}

        assert results[router] == [mw]

    def test_single_router_yields_own_base_filters(self):
        """Один роутер без родителей отдаёт только свои base_filters."""
        dp = Dispatcher()
        router = Router("r")
        f = AllowFilter()
        router.filter(f)
        dp.include_routers(router)

        results = {r: bfs for r, _, __, bfs in dp._iter_routers(dp.routers)}

        assert results[router] == [f]

    def test_child_inherits_parent_middlewares(self):
        """Дочерний роутер накапливает middleware родителя."""
        dp = Dispatcher()
        parent = Router("parent")
        child = Router("child")

        mw_p = TrackingMiddleware("p", [])
        mw_c = TrackingMiddleware("c", [])
        parent.middleware(mw_p)
        child.middleware(mw_c)
        parent.include_routers(child)
        dp.include_routers(parent)

        results = {r: mws for r, mws, *_ in dp._iter_routers(dp.routers)}

        assert results[child] == [mw_p, mw_c]

    def test_child_inherits_parent_base_filters(self):
        """Дочерний роутер накапливает base_filters родителя."""
        dp = Dispatcher()
        parent = Router("parent")
        child = Router("child")

        bf_p = AllowFilter()
        bf_c = AllowFilter()
        parent.filter(bf_p)
        child.filter(bf_c)
        parent.include_routers(child)
        dp.include_routers(parent)

        results = {r: bfs for r, _, __, bfs in dp._iter_routers(dp.routers)}

        assert results[child] == [bf_p, bf_c]

    def test_three_levels_accumulate_all_middlewares(self):
        """Три уровня вложенности — middleware накапливаются по всей цепочке."""
        dp = Dispatcher()
        r1 = Router("r1")
        r2 = Router("r2")
        r3 = Router("r3")

        mw1 = TrackingMiddleware("1", [])
        mw2 = TrackingMiddleware("2", [])
        mw3 = TrackingMiddleware("3", [])
        r1.middleware(mw1)
        r2.middleware(mw2)
        r3.middleware(mw3)

        r2.include_routers(r3)
        r1.include_routers(r2)
        dp.include_routers(r1)

        results = {r: mws for r, mws, *_ in dp._iter_routers(dp.routers)}

        assert results[r1] == [mw1]
        assert results[r2] == [mw1, mw2]
        assert results[r3] == [mw1, mw2, mw3]

    def test_three_levels_accumulate_all_base_filters(self):
        """Три уровня вложенности — base_filters накапливаются по всей цепочке."""
        dp = Dispatcher()
        r1 = Router("r1")
        r2 = Router("r2")
        r3 = Router("r3")

        bf1 = AllowFilter()
        bf2 = AllowFilter()
        bf3 = AllowFilter()
        r1.filter(bf1)
        r2.filter(bf2)
        r3.filter(bf3)

        r2.include_routers(r3)
        r1.include_routers(r2)
        dp.include_routers(r1)

        results = {r: bfs for r, _, __, bfs in dp._iter_routers(dp.routers)}

        assert results[r3] == [bf1, bf2, bf3]

    def test_dispatcher_self_not_accumulated_as_middleware_source(self):
        """
        Dispatcher-self исключается из накопления middleware.
        Его middleware применяются глобально через global_chain.
        """
        dp = Dispatcher()
        mw = TrackingMiddleware("dp", [])
        dp.middleware(mw)
        dp.routers.append(dp)

        results = {r: mws for r, mws, *_ in dp._iter_routers(dp.routers)}

        assert results[dp] == []

    def test_all_nested_routers_present_in_iteration(self):
        """_iter_routers обходит все вложенные роутеры, включая глубоко."""
        dp = Dispatcher()
        r1 = Router("r1")
        r2 = Router("r2")
        r3 = Router("r3")

        r2.include_routers(r3)
        r1.include_routers(r2)
        dp.include_routers(r1)

        found = {r for r, *_ in dp._iter_routers(dp.routers)}

        assert r1 in found
        assert r2 in found
        assert r3 in found

    def test_sibling_routers_do_not_share_middlewares(self):
        """Роутеры-соседи не накапливают middleware друг друга."""
        dp = Dispatcher()
        r_a = Router("a")
        r_b = Router("b")

        mw_a = TrackingMiddleware("a", [])
        r_a.middleware(mw_a)
        dp.include_routers(r_a, r_b)

        results = {r: mws for r, mws, *_ in dp._iter_routers(dp.routers)}

        assert mw_a not in results[r_b]
        assert results[r_b] == []

    def test_cycle_between_routers_does_not_recurse_infinitely(self):
        """
        Взаимное включение роутеров (a в b и b в a) не должно приводить к
        бесконечной рекурсии: полный обход _iter_routers остаётся конечным.
        """
        dp = Dispatcher()
        router_a = Router("a")
        router_b = Router("b")
        router_a.include_routers(router_b)
        router_b.include_routers(router_a)
        dp.include_routers(router_a)

        result = list(dp._iter_routers(dp.routers))
        routers_found = [r for r, *_ in result]

        assert len(result) == 2
        assert set(routers_found) == {router_a, router_b}


@pytest.mark.asyncio
class TestNestedRouterDispatch:
    """
    Интеграционные тесты вызова хендлеров во вложенных роутерах.
    """

    async def test_child_handler_is_called(self, sample_message_created_event):
        """Хендлер дочернего роутера вызывается при dispatch события."""
        dp = Dispatcher()
        parent = Router("parent")
        child = Router("child")
        called = []

        @child.message_created()
        async def handler(event):
            called.append("handler")

        parent.include_routers(child)
        dp.include_routers(parent)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert called == ["handler"]

    async def test_grandchild_handler_is_called(
        self, sample_message_created_event
    ):
        """Хендлер роутера третьего уровня вызывается корректно."""
        dp = Dispatcher()
        r1 = Router("r1")
        r2 = Router("r2")
        r3 = Router("r3")
        called = []

        @r3.message_created()
        async def handler(event):
            called.append("handler")

        r2.include_routers(r3)
        r1.include_routers(r2)
        dp.include_routers(r1)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert called == ["handler"]

    async def test_parent_handler_takes_priority_over_child(
        self, sample_message_created_event
    ):
        """
        Хендлер родительского роутера вызывается раньше дочернего
        и прекращает дальнейший поиск.
        """
        dp = Dispatcher()
        parent = Router("parent")
        child = Router("child")
        called = []

        @parent.message_created()
        async def parent_handler(event):
            called.append("parent")

        @child.message_created()
        async def child_handler(event):
            called.append("child")

        parent.include_routers(child)
        dp.include_routers(parent)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert called == ["parent"]

    async def test_message_created_router_is_not_processed_twice_when_duplicated(
        self, sample_message_created_event
    ):
        """
        Один и тот же экземпляр роутера не должен обрабатывать событие
        дважды, даже если включён в дерево роутеров в двух местах.
        """
        dp = Dispatcher()
        parent = Router("parent")
        shared = Router("shared")
        called = []

        @shared.message_created()
        async def handler(event):
            called.append("handler")

        parent.include_routers(shared)
        dp.include_routers(parent, shared)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert called == ["handler"]

    async def test_raw_response_router_is_not_processed_twice_when_duplicated(
        self,
    ):
        """
        Один и тот же экземпляр роутера не должен обрабатывать RAW событие
        дважды, даже если включён в дерево роутеров в двух местах.
        """
        from maxapi.enums.update import UpdateType

        dp = Dispatcher()
        parent = Router("parent")
        shared = Router("shared")
        called = []

        @shared.raw_api_response()
        async def handler(event):
            called.append("handler")

        parent.include_routers(shared)
        dp.include_routers(parent, shared)

        await dp.handle_raw_response(UpdateType.RAW_API_RESPONSE, {"k": "v"})

        assert called == ["handler"]

    async def test_prepare_handlers_warns_about_duplicated_routers(
        self, bot, caplog
    ):
        """
        При подготовке обработчиков должно логироваться предупреждение,
        если один и тот же экземпляр роутера включён в дерево несколько раз.
        """
        dp = Dispatcher()
        parent = Router("parent")
        shared = Router("shared")

        parent.include_routers(shared)
        dp.include_routers(parent, shared)

        dp._prepare_handlers(bot)

        warnings_text = "\n".join(
            r.message for r in caplog.records if r.levelname == "WARNING"
        )
        assert "повторные включения роутеров" in warnings_text.lower()


@pytest.mark.asyncio
class TestNestedMiddlewareInheritance:
    """
    Интеграционные тесты наследования middleware во вложенных роутерах.
    """

    async def test_parent_middleware_wraps_child_handler(
        self, sample_message_created_event
    ):
        """Middleware родителя оборачивает хендлер дочернего роутера."""
        dp = Dispatcher()
        parent = Router("parent")
        child = Router("child")
        log = []

        parent.middleware(TrackingMiddleware("parent", log))

        @child.message_created()
        async def handler(event):
            log.append("handler")

        parent.include_routers(child)
        dp.include_routers(parent)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert log == ["parent:before", "handler", "parent:after"]

    async def test_parent_and_child_middlewares_applied_in_order(
        self, sample_message_created_event
    ):
        """
        Middleware родителя и ребёнка применяются в порядке вложенности:
        родитель → ребёнок → хендлер → ребёнок → родитель.
        """
        dp = Dispatcher()
        parent = Router("parent")
        child = Router("child")
        log = []

        parent.middleware(TrackingMiddleware("parent", log))
        child.middleware(TrackingMiddleware("child", log))

        @child.message_created()
        async def handler(event):
            log.append("handler")

        parent.include_routers(child)
        dp.include_routers(parent)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert log == [
            "parent:before",
            "child:before",
            "handler",
            "child:after",
            "parent:after",
        ]

    async def test_three_levels_all_middlewares_wrap_deepest_handler(
        self, sample_message_created_event
    ):
        """
        Три уровня middleware оборачивают хендлер в правильном порядке:
        r1 → r2 → r3 → хендлер → r3 → r2 → r1.
        """
        dp = Dispatcher()
        r1 = Router("r1")
        r2 = Router("r2")
        r3 = Router("r3")
        log = []

        r1.middleware(TrackingMiddleware("r1", log))
        r2.middleware(TrackingMiddleware("r2", log))
        r3.middleware(TrackingMiddleware("r3", log))

        @r3.message_created()
        async def handler(event):
            log.append("handler")

        r2.include_routers(r3)
        r1.include_routers(r2)
        dp.include_routers(r1)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert log == [
            "r1:before",
            "r2:before",
            "r3:before",
            "handler",
            "r3:after",
            "r2:after",
            "r1:after",
        ]

    async def test_sibling_blocking_middleware_does_not_affect_other_router(
        self, sample_message_created_event
    ):
        """
        BlockingMiddleware одного роутера не блокирует хендлеры соседнего роутера:
        middleware изолированы в рамках своего роутера.
        """
        dp = Dispatcher()
        router_a = Router("a")
        router_b = Router("b")
        log = []

        router_a.middleware(BlockingMiddleware(log))

        @router_b.message_created()
        async def handler(event):
            log.append("handler")

        dp.include_routers(router_a, router_b)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert "handler" in log


@pytest.mark.asyncio
class TestNestedBaseFilterInheritance:
    """
    Интеграционные тесты наследования BaseFilter во вложенных роутерах.
    """

    async def test_parent_block_filter_blocks_child_handler(
        self, sample_message_created_event
    ):
        """BlockFilter родителя блокирует хендлер дочернего роутера."""
        dp = Dispatcher()
        parent = Router("parent")
        child = Router("child")
        called = []

        parent.filter(BlockFilter())

        @child.message_created()
        async def handler(event):
            called.append("handler")

        parent.include_routers(child)
        dp.include_routers(parent)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert called == []

    async def test_parent_allow_filter_passes_child_handler(
        self, sample_message_created_event
    ):
        """AllowFilter родителя пропускает хендлер дочернего роутера."""
        dp = Dispatcher()
        parent = Router("parent")
        child = Router("child")
        called = []

        parent.filter(AllowFilter())

        @child.message_created()
        async def handler(event):
            called.append("handler")

        parent.include_routers(child)
        dp.include_routers(parent)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert called == ["handler"]

    async def test_grandparent_block_filter_blocks_grandchild_handler(
        self, sample_message_created_event
    ):
        """BlockFilter уровня 1 блокирует хендлер уровня 3."""
        dp = Dispatcher()
        r1 = Router("r1")
        r2 = Router("r2")
        r3 = Router("r3")
        called = []

        r1.filter(BlockFilter())

        @r3.message_created()
        async def handler(event):
            called.append("handler")

        r2.include_routers(r3)
        r1.include_routers(r2)
        dp.include_routers(r1)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert called == []

    async def test_middle_level_block_filter_blocks_deepest_handler(
        self, sample_message_created_event
    ):
        """BlockFilter промежуточного уровня блокирует самый глубокий хендлер."""
        dp = Dispatcher()
        r1 = Router("r1")
        r2 = Router("r2")
        r3 = Router("r3")
        called = []

        r1.filter(AllowFilter())
        r2.filter(BlockFilter())

        @r3.message_created()
        async def handler(event):
            called.append("handler")

        r2.include_routers(r3)
        r1.include_routers(r2)
        dp.include_routers(r1)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert called == []

    async def test_three_levels_all_allow_filters_pass(
        self, sample_message_created_event
    ):
        """Три AllowFilter на трёх уровнях пропускают самый глубокий хендлер."""
        dp = Dispatcher()
        r1 = Router("r1")
        r2 = Router("r2")
        r3 = Router("r3")
        called = []

        r1.filter(AllowFilter())
        r2.filter(AllowFilter())
        r3.filter(AllowFilter())

        @r3.message_created()
        async def handler(event):
            called.append("handler")

        r2.include_routers(r3)
        r1.include_routers(r2)
        dp.include_routers(r1)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert called == ["handler"]

    async def test_child_block_filter_does_not_block_parent_handler(
        self, sample_message_created_event
    ):
        """BlockFilter дочернего роутера не влияет на хендлер родителя."""
        dp = Dispatcher()
        parent = Router("parent")
        child = Router("child")
        called = []

        child.filter(BlockFilter())

        @parent.message_created()
        async def handler(event):
            called.append("parent_handler")

        parent.include_routers(child)
        dp.include_routers(parent)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert called == ["parent_handler"]

    async def test_base_filter_data_injected_into_child_handler(
        self, sample_message_created_event
    ):
        """
        Данные, возвращённые BaseFilter родителя, доступны
        хендлеру дочернего роутера через именованный аргумент.
        """
        dp = Dispatcher()
        parent = Router("parent")
        child = Router("child")
        received = []

        parent.filter(DataFilter("injected", "from_parent"))

        @child.message_created()
        async def handler(event, injected: str):
            received.append(injected)

        parent.include_routers(child)
        dp.include_routers(parent)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert received == ["from_parent"]


@pytest.mark.asyncio
class TestNestedMagicFilterInheritance:
    """
    Интеграционные тесты наследования MagicFilter (F.xxx)
    во вложенных роутерах.
    """

    async def test_parent_magic_filter_passes_matching_child_handler(
        self, sample_message_created_event
    ):
        """MagicFilter родителя пропускает событие с совпадающим атрибутом."""
        from maxapi.enums.update import UpdateType
        from maxapi.filters import F

        dp = Dispatcher()
        parent = Router("parent")
        child = Router("child")
        called = []

        parent.filters.append(F.update_type == UpdateType.MESSAGE_CREATED)

        @child.message_created()
        async def handler(event):
            called.append("handler")

        parent.include_routers(child)
        dp.include_routers(parent)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert called == ["handler"]

    async def test_parent_magic_filter_blocks_non_matching_child_handler(
        self, sample_message_created_event
    ):
        """MagicFilter родителя блокирует событие с несовпадающим атрибутом."""
        from maxapi.enums.update import UpdateType
        from maxapi.filters import F

        dp = Dispatcher()
        parent = Router("parent")
        child = Router("child")
        called = []

        parent.filters.append(F.update_type == UpdateType.BOT_STARTED)

        @child.message_created()
        async def handler(event):
            called.append("handler")

        parent.include_routers(child)
        dp.include_routers(parent)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert called == []

    async def test_three_levels_magic_filter_blocks_grandchild_handler(
        self, sample_message_created_event
    ):
        """MagicFilter уровня 1 блокирует хендлер уровня 3."""
        from maxapi.enums.update import UpdateType
        from maxapi.filters import F

        dp = Dispatcher()
        r1 = Router("r1")
        r2 = Router("r2")
        r3 = Router("r3")
        called = []

        r1.filters.append(F.update_type == UpdateType.BOT_STARTED)

        @r3.message_created()
        async def handler(event):
            called.append("handler")

        r2.include_routers(r3)
        r1.include_routers(r2)
        dp.include_routers(r1)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert called == []

    async def test_three_levels_magic_filter_passes_grandchild_handler(
        self, sample_message_created_event
    ):
        """MagicFilter уровня 1 с совпадением пропускает хендлер уровня 3."""
        from maxapi.enums.update import UpdateType
        from maxapi.filters import F

        dp = Dispatcher()
        r1 = Router("r1")
        r2 = Router("r2")
        r3 = Router("r3")
        called = []

        r1.filters.append(F.update_type == UpdateType.MESSAGE_CREATED)

        @r3.message_created()
        async def handler(event):
            called.append("handler")

        r2.include_routers(r3)
        r1.include_routers(r2)
        dp.include_routers(r1)
        dp.routers.append(dp)

        await dp.handle(sample_message_created_event)

        assert called == ["handler"]
