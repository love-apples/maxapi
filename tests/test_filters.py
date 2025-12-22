"""Тесты для фильтров и команд."""

from unittest.mock import Mock

import pytest

# Core Stuff
from maxapi.filters.callback_payload import CallbackPayload
from maxapi.filters.command import Command
from maxapi.filters.filter import BaseFilter
from maxapi.types.updates.message_created import MessageCreated


class TestBaseFilter:
    """Тесты BaseFilter."""

    @pytest.mark.asyncio
    async def test_base_filter_default(self, sample_message_created_event):
        """Тест базового фильтра по умолчанию."""
        filter_obj = BaseFilter()
        result = await filter_obj(sample_message_created_event)
        assert result is True

    @pytest.mark.asyncio
    async def test_custom_filter_return_true(
        self, sample_message_created_event
    ):
        """Тест кастомного фильтра, возвращающего True."""

        class TestFilter(BaseFilter):
            async def __call__(self, event):
                return True

        filter_obj = TestFilter()
        result = await filter_obj(sample_message_created_event)
        assert result is True

    @pytest.mark.asyncio
    async def test_custom_filter_return_false(
        self, sample_message_created_event
    ):
        """Тест кастомного фильтра, возвращающего False."""

        class TestFilter(BaseFilter):
            async def __call__(self, event):
                return False

        filter_obj = TestFilter()
        result = await filter_obj(sample_message_created_event)
        assert result is False

    @pytest.mark.asyncio
    async def test_custom_filter_return_dict(
        self, sample_message_created_event
    ):
        """Тест кастомного фильтра, возвращающего словарь."""

        class TestFilter(BaseFilter):
            async def __call__(self, event):
                return {"test_key": "test_value"}

        filter_obj = TestFilter()
        result = await filter_obj(sample_message_created_event)
        assert isinstance(result, dict)
        assert result["test_key"] == "test_value"


class TestCommandFilter:
    """Тесты фильтра команд."""

    def test_command_filter_init(self):
        """Тест инициализации Command фильтра."""
        cmd = Command("start")
        assert "start" in cmd.commands

    def test_command_filter_multiple(self):
        """Тест Command с несколькими командами."""
        cmd = Command(["start", "begin", "go"])
        assert "start" in cmd.commands
        assert "begin" in cmd.commands
        assert "go" in cmd.commands

    @pytest.mark.asyncio
    async def test_command_filter_match(self):
        """Тест Command фильтра при совпадении."""
        # Core Stuff
        from maxapi.types.message import Message, MessageBody

        cmd = Command("start")

        # Создаем событие с командой /start
        event = Mock(spec=MessageCreated)
        message_body = Mock(spec=MessageBody)
        message_body.text = "/start"
        message = Mock(spec=Message)
        message.body = message_body
        event.message = message

        # Мокаем bot.me для корректной работы фильтра
        mock_bot = Mock()
        mock_me = Mock()
        mock_me.username = None
        mock_bot.me = mock_me
        event._ensure_bot = Mock(return_value=mock_bot)

        result = await cmd(event)

        # Command возвращает словарь с 'args' при совпадении
        assert result is not False
        assert isinstance(result, dict)
        assert "args" in result

    @pytest.mark.asyncio
    async def test_command_filter_no_match(self):
        """Тест Command фильтра при несовпадении."""
        # Core Stuff
        from maxapi.types.message import Message, MessageBody

        cmd = Command("start")

        # Создаем событие без команды
        event = Mock(spec=MessageCreated)
        message_body = Mock(spec=MessageBody)
        message_body.text = "just text"
        message = Mock(spec=Message)
        message.body = message_body
        event.message = message

        # Мокаем bot.me для корректной работы фильтра
        mock_bot = Mock()
        mock_me = Mock()
        mock_me.username = None
        mock_bot.me = mock_me
        event._ensure_bot = Mock(return_value=mock_bot)

        result = await cmd(event)

        assert result is False


class TestCallbackPayloadFilter:
    """Тесты фильтра CallbackPayload."""

    def test_callback_payload_init(self):
        """Тест инициализации PayloadFilter."""
        # Core Stuff
        from maxapi.filters.callback_payload import PayloadFilter

        # CallbackPayload - это BaseModel, используется через PayloadFilter
        # Создаем простой класс payload для теста
        class TestPayload(CallbackPayload):
            value: str

        payload_filter = PayloadFilter(model=TestPayload, rule=None)
        assert payload_filter.model == TestPayload
        assert payload_filter.rule is None

    @pytest.mark.asyncio
    async def test_callback_payload_match(self):
        """Тест PayloadFilter при совпадении."""
        # Core Stuff
        from maxapi.filters.callback_payload import PayloadFilter
        from maxapi.types.callback import Callback
        from maxapi.types.updates.message_callback import MessageCallback

        # Создаем простой класс payload для теста
        class TestPayload(CallbackPayload):
            value: str

        payload_filter = PayloadFilter(model=TestPayload, rule=None)

        # Создаем payload строку (prefix|value)
        payload_str = "TestPayload|test_value"

        callback = Mock(spec=Callback)
        callback.payload = payload_str

        event = Mock(spec=MessageCallback)
        event.callback = callback

        result = await payload_filter(event)

        assert result is not False
        assert isinstance(result, dict)
        assert "payload" in result
        assert isinstance(result["payload"], TestPayload)
        assert result["payload"].value == "test_value"

    @pytest.mark.asyncio
    async def test_callback_payload_no_match(self):
        """Тест PayloadFilter при несовпадении."""
        # Core Stuff
        from maxapi.filters.callback_payload import PayloadFilter
        from maxapi.types.callback import Callback
        from maxapi.types.updates.message_callback import MessageCallback

        # Создаем простой класс payload для теста
        class TestPayload(CallbackPayload):
            value: str

        payload_filter = PayloadFilter(model=TestPayload, rule=None)

        # Неправильный payload (неправильный prefix)
        callback = Mock(spec=Callback)
        callback.payload = "WrongPrefix|test_value"

        event = Mock(spec=MessageCallback)
        event.callback = callback

        result = await payload_filter(event)

        assert result is False
