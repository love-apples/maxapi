"""Тесты для MemoryStorage."""

import pytest


class TestMemoryContext:
    """Тесты MemoryStorage."""

    @pytest.mark.asyncio
    async def test_get_data_empty(self, sample_storage, sample_storage_key):
        """Тест получения пустых данных."""
        data = await sample_storage.get_data(key=sample_storage_key)
        assert data == {}

    @pytest.mark.asyncio
    async def test_set_data(self, sample_storage, sample_storage_key):
        """Тест установки данных."""
        test_data = {"key1": "value1", "key2": 42}
        await sample_storage.set_data(key=sample_storage_key, data=test_data)

        data = await sample_storage.get_data(key=sample_storage_key)
        assert data == test_data

    @pytest.mark.asyncio
    async def test_update_data(self, sample_storage, sample_storage_key):
        """Тест обновления данных."""
        await sample_storage.set_data(
            key=sample_storage_key, data={"key1": "value1"}
        )
        await sample_storage.update_data(
            key=sample_storage_key, key2="value2", key3=123
        )

        data = await sample_storage.get_data(key=sample_storage_key)
        assert data["key1"] == "value1"
        assert data["key2"] == "value2"
        assert data["key3"] == 123

    @pytest.mark.asyncio
    async def test_get_state_none(self, sample_storage, sample_storage_key):
        """Тест получения состояния (изначально None)."""
        state = await sample_storage.get_state(key=sample_storage_key)
        assert state is None

    @pytest.mark.asyncio
    async def test_set_state_string(self, sample_storage, sample_storage_key):
        """Тест установки строкового состояния."""
        await sample_storage.set_state(
            key=sample_storage_key, state="test_state"
        )
        state = await sample_storage.get_state(key=sample_storage_key)
        assert state == "test_state"

    @pytest.mark.asyncio
    async def test_set_state_none(self, sample_storage, sample_storage_key):
        """Тест сброса состояния."""
        await sample_storage.set_state(
            key=sample_storage_key, state="test_state"
        )
        await sample_storage.set_state(key=sample_storage_key, state=None)
        state = await sample_storage.get_state(key=sample_storage_key)
        assert state is None

    @pytest.mark.asyncio
    async def test_clear(self, sample_storage, sample_storage_key):
        """Тест очистки хранилища."""
        await sample_storage.set_data(
            key=sample_storage_key, data={"key": "value"}
        )
        await sample_storage.set_state(
            key=sample_storage_key, state="test_state"
        )

        await sample_storage.clear(key=sample_storage_key)

        data = await sample_storage.get_data(key=sample_storage_key)
        state = await sample_storage.get_state(key=sample_storage_key)

        assert data == {}
        assert state is None

    @pytest.mark.asyncio
    async def test_concurrent_access(self, sample_storage, sample_storage_key):
        """Тест параллельного доступа к хранилищу."""
        import asyncio

        async def update_data(key, value):
            await sample_storage.update_data(
                key=sample_storage_key, **{key: value}
            )

        # Параллельные обновления
        await asyncio.gather(
            update_data("key1", "value1"),
            update_data("key2", "value2"),
            update_data("key3", "value3"),
        )

        data = await sample_storage.get_data(key=sample_storage_key)
        assert "key1" in data
        assert "key2" in data
        assert "key3" in data
