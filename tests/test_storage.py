import time

from maxapi.context import MemoryContext, MemoryStorage, RedisStorage
from maxapi.dispatcher import Dispatcher


def test_memory_storage_reuses_context_for_same_key():
    storage = MemoryStorage()

    context1 = storage.get_context(1, 2)
    context2 = storage.get_context(1, 2)

    assert context1 is context2


def test_memory_storage_enforces_max_contexts():
    storage = MemoryStorage(
        context_ttl=None,
        max_contexts=2,
        cleanup_interval=0,
    )

    storage.get_context(1, 1)
    storage.get_context(2, 2)
    storage.get_context(3, 3)

    assert sorted(storage.get_cached_contexts()) == [(2, 2), (3, 3)]


def test_memory_storage_expires_old_contexts():
    storage = MemoryStorage(
        context_ttl=0.01,
        max_contexts=None,
        cleanup_interval=0,
    )

    storage.get_context(1, 1)
    time.sleep(0.02)
    storage.get_context(2, 2)
    storage._cleanup_now()

    assert sorted(storage.get_cached_contexts()) == [(2, 2)]


def test_dispatcher_accepts_new_memory_storage():
    dispatcher = Dispatcher(storage=MemoryStorage())

    context = dispatcher._Dispatcher__get_context(10, 20)

    assert isinstance(context, MemoryContext)
    assert dispatcher.contexts[(10, 20)] is context


def test_memory_context_get_data_returns_copy():
    context = MemoryContext(chat_id=1, user_id=2)
    original = {"nested": {"value": 1}}

    import asyncio

    asyncio.run(context.set_data(original))
    returned = asyncio.run(context.get_data())
    returned["other"] = 2

    stored = asyncio.run(context.get_data())
    assert "other" not in stored


def test_redis_storage_returns_redis_context():
    class DummyRedis:
        pass

    storage = RedisStorage(redis_client=DummyRedis())
    context = storage.get_context(1, 2)

    assert context.__class__.__name__ == "RedisContext"
