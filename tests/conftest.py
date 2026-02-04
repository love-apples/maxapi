"""Конфигурация и фикстуры для pytest."""

import os
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest

# Загружаем переменные окружения из .env файла
try:
    from dotenv import load_dotenv

    # Загружаем .env из корня проекта (на уровень выше tests/)
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    tests_env = Path(__file__).parent / ".env"

    # Пробуем загрузить .env из разных мест (приоритет: корень проекта, затем tests/)
    if env_file.exists():
        load_dotenv(env_file, override=True)
    elif tests_env.exists():
        load_dotenv(tests_env, override=True)
    else:
        # Пробуем загрузить из текущей директории
        load_dotenv(override=True)
except ImportError:
    # python-dotenv не установлен, пропускаем загрузку
    pass

# Core Stuff
from maxapi import Bot, Dispatcher
from maxapi.client.default import DefaultConnectionProperties


@pytest.fixture
def mock_bot_token():
    """Фикстура с тестовым токеном."""
    return "test_token_12345"


@pytest.fixture
def bot_token_from_env():
    """Фикстура для получения токена из окружения (для интеграционных тестов)."""
    return os.environ.get("MAX_BOT_TOKEN")


@pytest.fixture
def test_chat_id_from_env():
    """Фикстура для получения test_chat_id из окружения."""
    chat_id_str = os.environ.get("TEST_CHAT_ID")
    if chat_id_str:
        try:
            return int(chat_id_str)
        except ValueError:
            return None
    return None


@pytest.fixture
def mock_session():
    """Фикстура с мок-сессией aiohttp."""
    session = AsyncMock(spec=aiohttp.ClientSession)
    session.base_url = "https://platform-api.max.ru"
    session.headers = {}
    session.close = AsyncMock()
    session.request = AsyncMock()
    return session


@pytest.fixture
def bot(mock_bot_token):
    """Фикстура для создания экземпляра Bot без реальных запросов."""
    bot = Bot(token=mock_bot_token)
    bot.session = None  # Гарантируем, что сессия не создана
    return bot


@pytest.fixture
def bot_with_session(mock_bot_token, mock_session):
    """Фикстура для Bot с мок-сессией."""
    bot = Bot(token=mock_bot_token)
    bot.session = mock_session
    return bot


@pytest.fixture
def dispatcher():
    """Фикстура для создания Dispatcher."""
    return Dispatcher()


@pytest.fixture
def router():
    """Фикстура для создания Router."""
    # Core Stuff
    from maxapi.dispatcher import Router

    return Router(router_id="test_router")


@pytest.fixture
def default_connection():
    """Фикстура для DefaultConnectionProperties."""
    return DefaultConnectionProperties()


@pytest.fixture
def sample_message_created_event():
    """Фикстура с примером события MessageCreated."""
    # Core Stuff
    from maxapi.enums.update import UpdateType
    from maxapi.types.message import Message, MessageBody
    from maxapi.types.updates.message_created import MessageCreated

    # Создаем минимальную структуру события
    event = Mock(spec=MessageCreated)
    event.update_type = UpdateType.MESSAGE_CREATED
    event.timestamp = 1234567890
    event.chat_id = 12345
    event.user_id = 67890

    # Мок для message
    message_body = Mock(spec=MessageBody)
    message_body.mid = "msg_123"
    message_body.text = "Test message"

    message = Mock(spec=Message)
    message.body = message_body
    message.bot = None

    event.message = message

    # Метод get_ids для события
    event.get_ids = Mock(return_value=(12345, 67890))

    return event


@pytest.fixture
def sample_storage():
    """Фикстура для создания MemoryStorage."""

    from maxapi.storage import MemoryStorage

    return MemoryStorage()


@pytest.fixture
def memory_storage():
    """Фикстура для создания MemoryStorage."""

    from maxapi.storage import MemoryStorage

    return MemoryStorage()


@pytest.fixture
def redis_url():
    url = os.environ.get("redis_url")
    if url:
        return url
    pytest.skip(
        "Не указана переменная окружения `redis_url` для подключения к Redis "
    )


@pytest.fixture
async def redis_storage(redis_url: str):
    from redis.asyncio.connection import parse_url as parse_redis_url
    from _pytest.config import UsageError

    from maxapi.storage.redis import RedisStorage

    try:
        parse_redis_url(redis_url)
    except ValueError as e:
        raise UsageError(
            f"Неверная ссылка подключения к Redis URL {redis_url!r}: {e}"
        )
    storage = RedisStorage.from_url(redis_url)
    try:
        await storage.redis.info()
    except ConnectionError as e:
        pytest.fail(str(e))

    try:
        yield storage
    finally:
        conn = await storage.redis
        await conn.flushdb()
        await storage.close()


@pytest.fixture()
def storage(request):
    return request.getfixturevalue(request.param)


@pytest.fixture
def storage_key():
    """Фикстура для создания StorageKey."""

    from maxapi.storage import StorageKey

    return StorageKey(chat_id=12345, user_id=67890)


@pytest.fixture
def sample_none_storage_key():
    """Фикстура для создания пустого StorageKey."""

    from maxapi.storage import StorageKey

    return StorageKey(chat_id=None, user_id=None)


@pytest.fixture
def sample_context(sample_storage, sample_storage_key):
    """Фикстура для создания MemoryContext."""
    # Core Stuff
    from maxapi.context import MemoryContext

    return MemoryContext(storage=sample_storage, key=sample_storage_key)


@pytest.fixture
async def integration_bot(bot_token_from_env):
    """Фикстура для интеграционных тестов с реальным ботом.

    Использовать только при наличии реального токена.
    Автоматически закрывает сессию после теста.
    """
    if not bot_token_from_env:
        pytest.skip("MAX_BOT_TOKEN не установлен в окружении")

    bot = Bot(token=bot_token_from_env)

    try:
        yield bot
    finally:
        # Закрываем сессию после теста для предотвращения "Event loop is closed"
        if bot.session and not bot.session.closed:
            try:
                await bot.close_session()
            except Exception:
                # Игнорируем ошибки при закрытии, если event loop уже закрыт
                pass


@pytest.fixture(autouse=True)
def preserve_env_vars():
    """Сохраняет переменные окружения перед тестами и восстанавливает после."""
    # Сохраняем значение MAX_BOT_TOKEN ДО тестов (уже загруженного из .env)
    original_token = os.environ.get("MAX_BOT_TOKEN")

    yield

    # Восстанавливаем после теста
    if original_token:
        os.environ["MAX_BOT_TOKEN"] = original_token
    elif "MAX_BOT_TOKEN" in os.environ:
        # Если токен был установлен в тесте, но не был до этого - удаляем
        # Но только если он не был загружен из .env изначально
        pass
