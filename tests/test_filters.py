"""Тесты для фильтров и команд."""

import pytest
from unittest.mock import Mock

from maxapi.filters.filter import BaseFilter
from maxapi.filters.command import Command, CommandStart
from maxapi.types.updates.message_created import MessageCreated


class TestBaseFilter:
    """Тесты BaseFilter."""

    @pytest.mark.asyncio
    async def test_base_filter_default(self):
        """Тест базового фильтра по умолчанию."""
        class TestFilter(BaseFilter): ...
        with pytest.raises(TypeError):
            TestFilter()

    @pytest.mark.asyncio
    async def test_custom_filter_return_true(
        self, sample_message_created_event
    ):
        """Тест кастомного фильтра, возвращающего True."""

        class TestFilter(BaseFilter):
            def __call__(self, event):
                return True

        assert TestFilter()(sample_message_created_event) is True

    @pytest.mark.asyncio
    async def test_custom_filter_return_false(
        self, sample_message_created_event
    ):
        """Тест кастомного фильтра, возвращающего False."""

        class TestFilter(BaseFilter):
            def __call__(self, event):
                return False

        assert TestFilter()(sample_message_created_event) is False

class TestCommandFilter:
    """Тесты фильтра команд."""

    def test_command_start_filter(self):
        """Тест инициализации Command фильтра."""
        f, _ = CommandStart()
        assert "start" in f.commands

    def test_command_filter_multiple(self):
        """Тест Command с несколькими командами."""
        commands = ("start", "begin", "go")
        f, _ = Command(*commands)
        assert all(c in f.commands for c in commands)

    @pytest.mark.asyncio
    async def test_command_filter_match(self):
        """Тест Command фильтра при совпадении."""
        from maxapi.types.message import MessageBody, Message

        f, _ = CommandStart()

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

        result = f(event)

        # Command возвращает словарь с 'args' при совпадении
        assert result is True

    @pytest.mark.asyncio
    async def test_command_filter_no_match(self):
        """Тест Command фильтра при несовпадении."""
        from maxapi.types.message import MessageBody, Message

        f, _ = CommandStart()

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

        result = f(event)

        assert result is False
