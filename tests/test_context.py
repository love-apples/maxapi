"""Тесты для Context и State Machine."""

import pytest

from maxapi.context import MemoryContext
from maxapi.context.state_machine import State, StatesGroup


class TestMemoryContext:
    """Тесты MemoryContext."""

    def test_context_init(self):
        """Тест инициализации контекста."""
        context = MemoryContext(chat_id=12345, user_id=67890)
        assert context.chat_id == 12345
        assert context.user_id == 67890

    def test_context_init_none_ids(self):
        """Тест инициализации контекста с None."""
        context = MemoryContext(chat_id=None, user_id=None)
        assert context.chat_id is None
        assert context.user_id is None

    @pytest.mark.asyncio
    async def test_get_data_empty(self, sample_context):
        """Тест получения пустых данных."""
        data = await sample_context.get_data()
        assert data == {}

    @pytest.mark.asyncio
    async def test_set_data(self, sample_context):
        """Тест установки данных."""
        test_data = {"key1": "value1", "key2": 42}
        await sample_context.set_data(test_data)

        data = await sample_context.get_data()
        assert data == test_data

    @pytest.mark.asyncio
    async def test_update_data(self, sample_context):
        """Тест обновления данных."""
        await sample_context.set_data({"key1": "value1"})
        await sample_context.update_data(key2="value2", key3=123)

        data = await sample_context.get_data()
        assert data["key1"] == "value1"
        assert data["key2"] == "value2"
        assert data["key3"] == 123

    @pytest.mark.asyncio
    async def test_get_state_none(self, sample_context):
        """Тест получения состояния (изначально None)."""
        state = await sample_context.get_state()
        assert state is None

    @pytest.mark.asyncio
    async def test_set_state_string(self, sample_context):
        """Тест установки строкового состояния."""
        await sample_context.set_state("test_state")
        state = await sample_context.get_state()
        assert state == "test_state"

    @pytest.mark.asyncio
    async def test_set_state_none(self, sample_context):
        """Тест сброса состояния."""
        await sample_context.set_state("test_state")
        await sample_context.set_state(None)
        state = await sample_context.get_state()
        assert state is None

    @pytest.mark.asyncio
    async def test_clear(self, sample_context):
        """Тест очистки контекста."""
        await sample_context.set_data({"key": "value"})
        await sample_context.set_state("test_state")

        await sample_context.clear()

        data = await sample_context.get_data()
        state = await sample_context.get_state()

        assert data == {}
        assert state is None

    @pytest.mark.asyncio
    async def test_concurrent_access(self, sample_context):
        """Тест параллельного доступа к контексту."""
        import asyncio

        async def update_data(key, value):
            await sample_context.update_data(**{key: value})

        # Параллельные обновления
        await asyncio.gather(
            update_data("key1", "value1"),
            update_data("key2", "value2"),
            update_data("key3", "value3"),
        )

        data = await sample_context.get_data()
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
    async def test_state_in_context(self, sample_context):
        """Тест использования State в контексте."""

        class TestStates(StatesGroup):
            waiting = State()
            processing = State()
            completed = State()

        await sample_context.set_state(TestStates.waiting)
        state = await sample_context.get_state()

        assert state is TestStates.waiting
        assert str(state) == "TestStates:waiting"

        await sample_context.set_state(TestStates.processing)
        state = await sample_context.get_state()
        assert state is TestStates.processing
