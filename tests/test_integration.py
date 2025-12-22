"""Интеграционные тесты (требуют реальный токен бота).

Эти тесты выполняют реальные запросы к API MAX.
Для запуска необходимо установить переменную окружения MAX_BOT_TOKEN.
Опционально можно указать TEST_CHAT_ID для тестов работы с чатами.
"""

import pytest

# Core Stuff
from maxapi import Dispatcher

# Маркер для интеграционных тестов
pytestmark = pytest.mark.integration

# Используем фикстуры integration_bot и test_chat_id_from_env из conftest.py


@pytest.fixture
async def test_chat_id(integration_bot, test_chat_id_from_env):
    """Получение тестового chat_id.

    Приоритет:
    1. Из переменной окружения TEST_CHAT_ID (или .env файла)
    2. Из первого чата в списке чатов бота
    """
    # Сначала проверяем переменную окружения
    if test_chat_id_from_env:
        return test_chat_id_from_env

    # Если не указан в окружении, пытаемся получить из списка чатов
    try:
        chats = await integration_bot.get_chats(count=1)
        if chats.chats and len(chats.chats) > 0:
            return chats.chats[0].chat_id
        return None
    except Exception:
        return None


class TestBotIntegration:
    """Интеграционные тесты Bot."""

    @pytest.mark.asyncio
    async def test_get_me(self, integration_bot):
        """Тест получения информации о боте."""
        me = await integration_bot.get_me()

        assert me is not None
        assert me.user_id is not None
        assert me.is_bot is True
        # _me устанавливается только в Dispatcher.check_me(), не в Bot.get_me()
        # Проверяем только корректность возвращаемых данных

    @pytest.mark.asyncio
    async def test_get_chats(self, integration_bot):
        """Тест получения списка чатов."""
        chats = await integration_bot.get_chats(count=5)

        assert chats is not None
        assert hasattr(chats, "chats")
        assert isinstance(chats.chats, list)

    @pytest.mark.asyncio
    async def test_get_subscriptions(self, integration_bot):
        """Тест получения подписок."""
        subs = await integration_bot.get_subscriptions()

        assert subs is not None
        assert hasattr(subs, "subscriptions")
        assert isinstance(subs.subscriptions, list)

    @pytest.mark.asyncio
    async def test_get_updates(self, integration_bot):
        """Тест получения обновлений."""
        updates = await integration_bot.get_updates(limit=1, timeout=1)

        assert updates is not None
        assert isinstance(updates, dict)

    @pytest.mark.asyncio
    async def test_get_chat_by_id(self, integration_bot, test_chat_id):
        """Тест получения чата по ID."""
        if not test_chat_id:
            pytest.skip("Не удалось получить test_chat_id")

        chat = await integration_bot.get_chat_by_id(test_chat_id)

        assert chat is not None
        assert chat.chat_id == test_chat_id

    @pytest.mark.asyncio
    async def test_get_upload_url(self, integration_bot):
        """Тест получения URL для загрузки."""
        # Core Stuff
        from maxapi.enums.upload_type import UploadType

        upload_info = await integration_bot.get_upload_url(UploadType.IMAGE)

        assert upload_info is not None
        assert hasattr(upload_info, "url")
        assert upload_info.url is not None


@pytest.mark.asyncio
class TestMessageIntegration:
    """Интеграционные тесты для работы с сообщениями."""

    async def test_send_message(self, integration_bot, test_chat_id):
        """Тест отправки сообщения."""
        if not test_chat_id:
            pytest.skip("Не удалось получить test_chat_id")

        message = await integration_bot.send_message(
            chat_id=test_chat_id, text="Тестовое сообщение из pytest"
        )

        assert message is not None
        assert message.message is not None
        assert message.message.body.mid is not None

    async def test_send_message_with_formatting(
        self, integration_bot, test_chat_id
    ):
        """Тест отправки сообщения с форматированием."""
        if not test_chat_id:
            pytest.skip("Не удалось получить test_chat_id")

        # Core Stuff
        from maxapi.enums.parse_mode import ParseMode

        message = await integration_bot.send_message(
            chat_id=test_chat_id,
            text="**Жирный** текст",
            parse_mode=ParseMode.MARKDOWN,
        )

        assert message is not None

    async def test_send_action(self, integration_bot, test_chat_id):
        """Тест отправки действия."""
        if not test_chat_id:
            pytest.skip("Не удалось получить test_chat_id")

        # Core Stuff
        from maxapi.enums.sender_action import SenderAction

        result = await integration_bot.send_action(
            chat_id=test_chat_id, action=SenderAction.TYPING_ON
        )

        assert result is not None


@pytest.mark.asyncio
class TestDispatcherIntegration:
    """Интеграционные тесты Dispatcher."""

    async def test_dispatcher_check_me(self, integration_bot):
        """Тест check_me в Dispatcher."""
        dp = Dispatcher()
        dp.bot = integration_bot

        await dp.check_me()

        # check_me() устанавливает _me
        assert integration_bot._me is not None
        assert integration_bot.me is not None
