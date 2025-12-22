"""Тесты для класса Bot."""

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Core Stuff
from maxapi import Bot
from maxapi.client.default import DefaultConnectionProperties
from maxapi.enums.parse_mode import ParseMode
from maxapi.enums.sender_action import SenderAction
from maxapi.exceptions.max import InvalidToken


class TestBotInitialization:
    """Тесты инициализации Bot."""

    def test_bot_init_with_token(self, mock_bot_token):
        """Тест создания бота с токеном."""
        bot = Bot(token=mock_bot_token)
        # Проверяем через headers, так как _Bot__token приватный
        assert bot.headers["Authorization"] == mock_bot_token

    def test_bot_init_from_env(self, monkeypatch):
        """Тест создания бота из переменной окружения."""
        test_token = "env_token_12345"
        monkeypatch.setenv("MAX_BOT_TOKEN", test_token)
        bot = Bot()
        # Проверяем через headers, так как _Bot__token приватный
        assert bot.headers["Authorization"] == test_token

    def test_bot_init_no_token(self):
        """Тест создания бота без токена (должна быть ошибка)."""
        # Временно убираем токен из окружения
        original_token = os.environ.pop("MAX_BOT_TOKEN", None)
        try:
            with pytest.raises(InvalidToken, match="Токен не может быть None"):
                Bot()
        finally:
            # Восстанавливаем токен
            if original_token:
                os.environ["MAX_BOT_TOKEN"] = original_token

    def test_bot_init_with_parse_mode(self, mock_bot_token):
        """Тест создания бота с parse_mode."""
        bot = Bot(token=mock_bot_token, parse_mode=ParseMode.MARKDOWN)
        assert bot.parse_mode == ParseMode.MARKDOWN

    def test_bot_init_with_notify(self, mock_bot_token):
        """Тест создания бота с notify."""
        bot = Bot(token=mock_bot_token, notify=False)
        assert bot.notify is False

    def test_bot_init_with_disable_link_preview(self, mock_bot_token):
        """Тест создания бота с disable_link_preview."""
        bot = Bot(token=mock_bot_token, disable_link_preview=True)
        assert bot.disable_link_preview is True

    def test_bot_init_with_default_connection(self, mock_bot_token):
        """Тест создания бота с custom connection properties."""
        connection = DefaultConnectionProperties()
        bot = Bot(token=mock_bot_token, default_connection=connection)
        assert bot.default_connection is connection

    def test_bot_init_after_input_media_delay(self, mock_bot_token):
        """Тест создания бота с custom задержкой после медиа."""
        bot = Bot(token=mock_bot_token, after_input_media_delay=5.0)
        assert bot.after_input_media_delay == 5.0

    def test_bot_init_auto_check_subscriptions(self, mock_bot_token):
        """Тест создания бота с auto_check_subscriptions."""
        bot = Bot(token=mock_bot_token, auto_check_subscriptions=False)
        assert bot.auto_check_subscriptions is False


class TestBotProperties:
    """Тесты свойств Bot."""

    def test_handlers_commands_property(self, bot):
        """Тест свойства handlers_commands."""
        assert isinstance(bot.handlers_commands, list)
        assert bot.handlers_commands == bot.commands

    def test_me_property(self, bot):
        """Тест свойства me."""
        assert bot.me is None
        # После вызова get_me() должно быть установлено
        # (это проверяется в интеграционных тестах)


class TestBotResolveMethods:
    """Тесты методов разрешения параметров."""

    def test_resolve_notify(self, bot):
        """Тест _resolve_notify."""
        bot.notify = True
        assert bot._resolve_notify(None) is True
        assert bot._resolve_notify(False) is False
        assert bot._resolve_notify(True) is True

    def test_resolve_parse_mode(self, bot):
        """Тест _resolve_parse_mode."""
        bot.parse_mode = ParseMode.MARKDOWN
        assert bot._resolve_parse_mode(None) == ParseMode.MARKDOWN
        assert bot._resolve_parse_mode(ParseMode.HTML) == ParseMode.HTML

    def test_resolve_disable_link_preview(self, bot):
        """Тест _resolve_disable_link_preview."""
        bot.disable_link_preview = True
        assert bot._resolve_disable_link_preview(None) is True
        assert bot._resolve_disable_link_preview(False) is False


class TestBotSessionManagement:
    """Тесты управления сессией."""

    @pytest.mark.asyncio
    async def test_close_session(self, bot_with_session):
        """Тест закрытия сессии."""
        await bot_with_session.close_session()
        bot_with_session.session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_session_none(self, bot):
        """Тест закрытия сессии, когда её нет."""
        # Не должно быть ошибки
        await bot.close_session()


class TestBotMethods:
    """Тесты методов Bot (моки)."""

    @pytest.mark.asyncio
    async def test_send_message_call(self, bot):
        """Тест вызова send_message (без реального запроса)."""
        # Core Stuff
        from maxapi.methods.send_message import SendMessage

        with patch.object(
            SendMessage, "fetch", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = Mock(
                message=Mock(body=Mock(mid="msg_123"))
            )

            await bot.send_message(chat_id=12345, text="Test message")

            assert mock_fetch.called

    @pytest.mark.asyncio
    async def test_send_action_call(self, bot):
        """Тест вызова send_action (без реального запроса)."""
        # Core Stuff
        from maxapi.methods.send_action import SendAction

        with patch.object(
            SendAction, "fetch", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = Mock()

            await bot.send_action(chat_id=12345, action=SenderAction.TYPING_ON)

            assert mock_fetch.called

    @pytest.mark.asyncio
    async def test_get_me_structure(self, bot):
        """Тест структуры вызова get_me."""
        # Core Stuff
        from maxapi.methods.get_me import GetMe

        with patch.object(
            GetMe, "fetch", new_callable=AsyncMock
        ) as mock_fetch:
            mock_user = Mock()
            mock_user.user_id = 123
            mock_user.username = "test_bot"
            mock_fetch.return_value = mock_user

            result = await bot.get_me()

            assert mock_fetch.called
            # Проверяем, что результат возвращен
            assert result == mock_user
            # _me устанавливается в GetMe.fetch, но в моке этого не происходит
            # Это нормально, так как мы мокируем весь fetch


class TestBotIntegration:
    """Интеграционные тесты Bot (требуют реальный токен)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_me_integration(self, integration_bot):
        """Интеграционный тест get_me."""
        me = await integration_bot.get_me()
        assert me is not None
        assert me.user_id is not None
        assert me.is_bot is True
        # _me устанавливается в Dispatcher.check_me(), но не в Bot.get_me()
        # Проверяем только что метод возвращает корректные данные

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_subscriptions_integration(self, integration_bot):
        """Интеграционный тест get_subscriptions."""
        subs = await integration_bot.get_subscriptions()
        assert subs is not None
        assert hasattr(subs, "subscriptions")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_chats_integration(self, integration_bot):
        """Интеграционный тест get_chats."""
        chats = await integration_bot.get_chats(count=5)
        assert chats is not None
        assert hasattr(chats, "chats")

    @pytest.mark.asyncio
    async def test_close_session_cleanup(self, integration_bot):
        """Интеграционный тест правильного закрытия сессии."""
        # Создаем сессию
        await integration_bot.get_me()
        assert integration_bot.session is not None

        # Закрываем сессию
        await integration_bot.close_session()
        # close_session() закрывает сессию, но не устанавливает session = None
        # Проверяем, что сессия закрыта (если еще существует)
        if integration_bot.session:
            assert integration_bot.session.closed
