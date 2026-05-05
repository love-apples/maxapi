"""Тесты для Dispatcher и Router"""

import logging
import warnings
from unittest.mock import AsyncMock, Mock, patch

import pytest
from maxapi import Bot, Dispatcher
from maxapi.dispatcher import Router
from maxapi.enums.update import UpdateType


@pytest.fixture
def dp():
    return Dispatcher(router_id="test_dp")


@pytest.fixture
def bot(mock_bot_token):
    b = Bot(token=mock_bot_token)
    b.session = None
    return b


class TestEventRegister:
    def test_register_adds_handler(self, dp):
        """Event.register добавляет обработчик в router.event_handlers."""

        async def handler(event): ...

        dp.message_created.register(handler)
        assert len(dp.event_handlers) == 1
        assert dp.event_handlers[0].func_event is handler

    def test_call_decorator_adds_handler(self, dp):
        """Event.__call__ работает как декоратор."""

        @dp.message_created()
        async def handler(event): ...

        assert len(dp.event_handlers) == 1
        assert dp.event_handlers[0].func_event is handler

    def test_register_with_state(self, dp):
        """Event.register с states=[...] правильно передаёт их в Handler."""

        async def handler(event): ...

        dp.message_created.register(handler, states=["state_a"])
        assert dp.event_handlers[0].states == ["state_a"]

    def test_register_deprecated_warns(self, dp):
        """Регистрация deprecated-события выдаёт DeprecationWarning."""

        async def handler(event): ...

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            dp.message_chat_created.register(handler)
            assert any(issubclass(x.category, DeprecationWarning) for x in w)

    def test_on_started_sets_func(self, dp):
        """Регистрация через on_started устанавливает on_started_func."""

        async def started(): ...

        dp.on_started.register(started)
        assert dp.on_started_func is started

    def test_multiple_event_types(self, dp):
        """Регистрация разных событий — обработчики не мешают друг другу."""

        async def h1(event): ...
        async def h2(event): ...

        dp.message_created.register(h1)
        dp.message_edited.register(h2)

        types = [h.update_type for h in dp.event_handlers]
        assert UpdateType.MESSAGE_CREATED in types
        assert UpdateType.MESSAGE_EDITED in types

    def test_bot_added_handler_registered(self, dp):
        """Регистрация обработчика bot_added работает корректно."""

        async def handler(event): ...

        dp.bot_added.register(handler)
        assert any(
            h.update_type == UpdateType.BOT_ADDED for h in dp.event_handlers
        )

    def test_bot_started_handler_registered(self, dp):
        """Регистрация обработчика bot_started работает корректно."""

        async def handler(event): ...

        @dp.bot_started()
        async def h(event): ...

        assert any(
            h.update_type == UpdateType.BOT_STARTED for h in dp.event_handlers
        )

    def test_message_callback_registered(self, dp):
        """Регистрация обработчика message_callback."""

        @dp.message_callback()
        async def handler(event): ...

        assert any(
            h.update_type == UpdateType.MESSAGE_CALLBACK
            for h in dp.event_handlers
        )


class TestDispatcherConfig:
    def test_filter_appends(self, dp):
        """Dispatcher.filter добавляет BaseFilter в base_filters."""
        mock_filter = Mock()
        dp.filter(mock_filter)
        assert mock_filter in dp.base_filters

    def test_include_routers(self, dp):
        """Dispatcher.include_routers добавляет роутеры в список."""
        r1 = Router(router_id="r1")
        r2 = Router(router_id="r2")
        dp.include_routers(r1, r2)
        assert r1 in dp.routers
        assert r2 in dp.routers

    def test_multiple_filters(self, dp):
        """Множество фильтров добавляются все."""
        f1 = Mock()
        f2 = Mock()
        dp.filter(f1)
        dp.filter(f2)
        assert f1 in dp.base_filters
        assert f2 in dp.base_filters


class TestStopPolling:
    @pytest.mark.asyncio
    async def test_stop_polling_sets_flag_false(self, dp):
        """stop_polling устанавливает polling=False."""
        dp.polling = True
        await dp.stop_polling()
        assert dp.polling is False

    @pytest.mark.asyncio
    async def test_stop_polling_when_already_stopped(self, dp):
        """stop_polling не падает, если polling уже False."""
        dp.polling = False
        await dp.stop_polling()
        assert dp.polling is False


class TestBuildMiddlewareChain:
    @pytest.mark.asyncio
    async def test_chain_without_middlewares(self, dp):
        """build_middleware_chain без middleware просто вызывает handler."""
        called = []

        async def handler(event, data):
            called.append("handler")

        chain = dp.build_middleware_chain([], handler)
        await chain("event", {})
        assert called == ["handler"]

    @pytest.mark.asyncio
    async def test_chain_with_middleware(self, dp):
        """build_middleware_chain оборачивает handler в middleware."""
        order = []

        class TracingMiddleware:
            async def __call__(self, handler, event, data):
                order.append("before")
                await handler(event, data)
                order.append("after")

        async def handler(event, data):
            order.append("handler")

        chain = dp.build_middleware_chain([TracingMiddleware()], handler)
        await chain("event", {})
        assert order == ["before", "handler", "after"]

    @pytest.mark.asyncio
    async def test_chain_multiple_middlewares(self, dp):
        """Несколько middleware выполняются в правильном порядке."""
        order = []

        class MW:
            def __init__(self, name):
                self.name = name

            async def __call__(self, handler, event, data):
                order.append(f"before_{self.name}")
                await handler(event, data)
                order.append(f"after_{self.name}")

        async def handler(event, data):
            order.append("handler")

        chain = dp.build_middleware_chain([MW("a"), MW("b")], handler)
        await chain("event", {})
        assert order == [
            "before_a",
            "before_b",
            "handler",
            "after_b",
            "after_a",
        ]


class TestCheckSubscriptions:
    @pytest.mark.asyncio
    async def test_no_subscriptions_no_warning(self, bot, caplog):
        """Если подписок нет — предупреждений в лог не пишется."""
        subs_mock = Mock()
        subs_mock.subscriptions = []

        with (
            patch.object(
                bot, "get_subscriptions", new=AsyncMock(return_value=subs_mock)
            ),
            caplog.at_level(logging.WARNING),
        ):
            await Dispatcher._check_subscriptions(bot)
        assert "ИГНОРИРУЕТ POLLING" not in caplog.text

    @pytest.mark.asyncio
    async def test_with_subscriptions_logs_warning(self, bot, caplog):
        """Если подписки есть — пишется WARNING в лог."""
        sub = Mock()
        sub.url = "https://example.com/hook"

        subs_mock = Mock()
        subs_mock.subscriptions = [sub]

        with (
            patch.object(
                bot, "get_subscriptions", new=AsyncMock(return_value=subs_mock)
            ),
            caplog.at_level(logging.WARNING),
        ):
            await Dispatcher._check_subscriptions(bot)
        assert "ИГНОРИРУЕТ POLLING" in caplog.text


class TestRouter:
    def test_router_inherits_dispatcher(self):
        """Router является подклассом Dispatcher."""
        r = Router(router_id="my_router")
        assert isinstance(r, Dispatcher)
        assert r.router_id == "my_router"

    def test_router_has_events(self):
        """Router содержит все события (унаследованные от Dispatcher)."""
        r = Router()
        assert hasattr(r, "message_created")
        assert hasattr(r, "message_edited")
        assert hasattr(r, "bot_started")

    def test_router_register_handler(self):
        """Регистрация обработчика через Router."""
        r = Router(router_id="r")

        @r.message_created()
        async def handler(event): ...

        assert len(r.event_handlers) == 1

    def test_router_without_id(self):
        """Router создаётся без router_id."""
        r = Router()
        assert r.router_id is None

    def test_router_include_in_dispatcher(self):
        """Router можно добавить в Dispatcher через include_routers."""
        dp = Dispatcher()
        r = Router(router_id="child")
        dp.include_routers(r)
        assert r in dp.routers


class TestBotResolvers:
    def test_resolve_notify_local_overrides(self, bot):
        """Локальный notify=False перекрывает bot.notify=True."""
        bot.notify = True
        result = bot._resolve_notify(notify=False)
        assert result is False

    def test_resolve_notify_falls_back_to_bot(self, bot):
        """При notify=None возвращается bot.notify."""
        bot.notify = True
        result = bot._resolve_notify(notify=None)
        assert result is True

    def test_resolve_notify_both_none(self, bot):
        """Если оба None — возвращается None."""
        bot.notify = None
        result = bot._resolve_notify(notify=None)
        assert result is None

    def test_resolve_parse_mode_local(self, bot):
        """Локальный parse_mode перекрывает bot.parse_mode."""
        from maxapi.enums.parse_mode import ParseMode

        bot.parse_mode = ParseMode.HTML
        result = bot._resolve_parse_mode(ParseMode.MARKDOWN)
        assert result == ParseMode.MARKDOWN

    def test_resolve_parse_mode_fallback(self, bot):
        """При mode=None возвращается bot.parse_mode."""
        from maxapi.enums.parse_mode import ParseMode

        bot.parse_mode = ParseMode.HTML
        result = bot._resolve_parse_mode(None)
        assert result == ParseMode.HTML

    def test_resolve_disable_link_preview_local(self, bot):
        """Локальный disable_link_preview=False перекрывает bot-значение."""
        bot.disable_link_preview = True
        result = bot._resolve_disable_link_preview(disable_link_preview=False)
        assert result is False

    def test_resolve_disable_link_preview_fallback(self, bot):
        """При None возвращается bot.disable_link_preview."""
        bot.disable_link_preview = True
        result = bot._resolve_disable_link_preview(disable_link_preview=None)
        assert result is True

    def test_handlers_commands_empty(self, bot):
        """handlers_commands возвращает пустой список по умолчанию."""
        assert bot.handlers_commands == []

    def test_me_property_none_by_default(self, bot):
        """Свойство me возвращает None до инициализации."""
        assert bot.me is None
