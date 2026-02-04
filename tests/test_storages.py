"""Тесты для MemoryStorage."""

import pytest

from maxapi.storage.base import BaseStorage, StorageKey


@pytest.mark.parametrize(
    "storage",
    ["memory_storage", "redis_storage"],
    indirect=True,
)
class TestMemoryStorages:
    """Тесты для реализаций BaseStorage."""

    @pytest.mark.asyncio
    async def test_get_data_empty(
        self, storage: BaseStorage, storage_key: StorageKey
    ):
        """Тест получения пустых данных."""
        data = await storage.get_data(key=storage_key)
        assert data == {}

    @pytest.mark.asyncio
    async def test_set_data(
        self, storage: BaseStorage, storage_key: StorageKey
    ):
        """Тест установки данных."""
        test_data = {"key1": "value1", "key2": 42}
        await storage.set_data(key=storage_key, data=test_data)

        data = await storage.get_data(key=storage_key)
        assert data == test_data

    @pytest.mark.asyncio
    async def test_update_data(
        self, storage: BaseStorage, storage_key: StorageKey
    ):
        """Тест обновления данных."""
        await storage.set_data(key=storage_key, data={"key1": "value1"})
        await storage.update_data(key=storage_key, key2="value2", key3=123)

        data = await storage.get_data(key=storage_key)
        assert data["key1"] == "value1"
        assert data["key2"] == "value2"
        assert data["key3"] == 123

    @pytest.mark.asyncio
    async def test_get_state_none(
        self, storage: BaseStorage, storage_key: StorageKey
    ):
        """Тест получения состояния (изначально None)."""
        state = await storage.get_state(key=storage_key)
        assert state is None

    @pytest.mark.asyncio
    async def test_set_state_string(
        self, storage: BaseStorage, storage_key: StorageKey
    ):
        """Тест установки строкового состояния."""
        await storage.set_state(key=storage_key, state="test_state")
        state = await storage.get_state(key=storage_key)
        assert state == "test_state"

    @pytest.mark.asyncio
    async def test_set_state_none(
        self, storage: BaseStorage, storage_key: StorageKey
    ):
        """Тест сброса состояния."""
        await storage.set_state(key=storage_key, state="test_state")
        await storage.set_state(key=storage_key, state=None)
        state = await storage.get_state(key=storage_key)
        assert state is None

    @pytest.mark.asyncio
    async def test_clear(self, storage: BaseStorage, storage_key: StorageKey):
        """Тест очистки хранилища."""
        await storage.set_data(key=storage_key, data={"key": "value"})
        await storage.set_state(key=storage_key, state="test_state")

        await storage.clear(key=storage_key)

        data = await storage.get_data(key=storage_key)
        state = await storage.get_state(key=storage_key)

        assert data == {}
        assert state is None

    @pytest.mark.asyncio
    async def test_concurrent_access(
        self, storage: BaseStorage, storage_key: StorageKey
    ):
        """Тест параллельного доступа к хранилищу."""
        import asyncio

        async def update_data(key, value):
            await storage.update_data(key=storage_key, **{key: value})

        # Параллельные обновления
        await asyncio.gather(
            update_data("key1", "value1"),
            update_data("key2", "value2"),
            update_data("key3", "value3"),
        )

        data = await storage.get_data(key=storage_key)
        assert "key1" in data
        assert "key2" in data
        assert "key3" in data
