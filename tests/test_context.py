"""Тесты для Context и State Machine."""

import pytest

from maxapi.context import Context
from maxapi.context.state_machine import State, StatesGroup
from maxapi.storage import MemoryStorage


class TestContext:
    """Тесты Context."""

    def test_context_init(self, memory_storage: MemoryStorage, storage_key):
        """Тест инициализации контекста."""

        context = Context(storage=memory_storage, key=storage_key)
        assert context.key == storage_key
        assert context.storage is memory_storage

    def test_context_init_none_ids(
        self, memory_storage: MemoryStorage, none_storage_key
    ):
        """Тест инициализации контекста с None."""
        context = Context(storage=memory_storage, key=none_storage_key)
        assert context.key == none_storage_key
        assert context.storage is memory_storage

    @pytest.mark.asyncio
    async def test_get_data_empty(self, context):
        """Тест получения пустых данных."""
        data = await context.get_data()
        assert data == {}

    @pytest.mark.asyncio
    async def test_set_data(self, context):
        """Тест установки данных."""
        test_data = {"key1": "value1", "key2": 42}
        await context.set_data(test_data)

        data = await context.get_data()
        assert data == test_data

    @pytest.mark.asyncio
    async def test_update_data(self, context):
        """Тест обновления данных."""
        await context.set_data({"key1": "value1"})
        await context.update_data(key2="value2", key3=123)

        data = await context.get_data()
        assert data["key1"] == "value1"
        assert data["key2"] == "value2"
        assert data["key3"] == 123

    @pytest.mark.asyncio
    async def test_get_state_none(self, context):
        """Тест получения состояния (изначально None)."""
        state = await context.get_state()
        assert state is None

    @pytest.mark.asyncio
    async def test_set_state_string(self, context):
        """Тест установки строкового состояния."""
        await context.set_state("test_state")
        state = await context.get_state()
        assert state == "test_state"

    @pytest.mark.asyncio
    async def test_set_state_none(self, context):
        """Тест сброса состояния."""
        await context.set_state("test_state")
        await context.set_state(None)
        state = await context.get_state()
        assert state is None

    @pytest.mark.asyncio
    async def test_clear(self, context):
        """Тест очистки контекста."""
        await context.set_data({"key": "value"})
        await context.set_state("test_state")

        await context.clear()

        data = await context.get_data()
        state = await context.get_state()

        assert data == {}
        assert state is None

    @pytest.mark.asyncio
    async def test_concurrent_access(self, context):
        """Тест параллельного доступа к контексту."""
        import asyncio

        async def update_data(key, value):
            await context.update_data(**{key: value})

        # Параллельные обновления
        await asyncio.gather(
            update_data("key1", "value1"),
            update_data("key2", "value2"),
            update_data("key3", "value3"),
        )

        data = await context.get_data()
        assert "key1" in data
        assert "key2" in data
        assert "key3" in data


class TestStateMachine:
    """Тесты State Machine."""

    def test_state_init(self):
        """Тест инициализации State."""
        state = State()
        assert state.name is None

    def test_state_set_name(self):
        """Тест установки имени State через __set_name__."""

        class TestStatesGroup(StatesGroup):
            state1 = State()
            state2 = State()

        assert str(TestStatesGroup.state1) == "TestStatesGroup:state1"
        assert str(TestStatesGroup.state2) == "TestStatesGroup:state2"

    def test_states_group_states_method(self):
        """Тест метода states() в StatesGroup."""

        class TestStatesGroup(StatesGroup):
            state1 = State()
            state2 = State()
            state3 = State()

        states = TestStatesGroup.states()
        assert isinstance(states, list)
        assert len(states) == 3
        assert "TestStatesGroup:state1" in states
        assert "TestStatesGroup:state2" in states
        assert "TestStatesGroup:state3" in states

    def test_states_group_without_states(self):
        """Тест StatesGroup без состояний."""

        class EmptyStatesGroup(StatesGroup):
            pass

        states = EmptyStatesGroup.states()
        assert states == []

    @pytest.mark.asyncio
    async def test_state_in_context(self, context):
        """Тест использования State в контексте."""

        class TestStates(StatesGroup):
            waiting = State()
            processing = State()
            completed = State()

        await context.set_state(TestStates.waiting)
        state = await context.get_state()

        assert state is TestStates.waiting
        assert str(state) == "TestStates:waiting"

        await context.set_state(TestStates.processing)
        state = await context.get_state()
        assert state is TestStates.processing
