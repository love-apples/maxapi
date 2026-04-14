"""Тесты для Context и State Machine."""

import asyncio

import pytest
from maxapi.context import MemoryContext
from maxapi.context.state_machine import State, StatesGroup
from maxapi.context.ttl import TTLTracker


class TestTTLTracker:
    """Тесты TTLTracker."""

    def test_ttl_tracker_init(self):
        """TTL сохраняется в трекере."""
        tracker = TTLTracker(60)
        assert tracker.ttl == 60

    def test_ttl_tracker_init_invalid_value(self):
        """Некорректный TTL вызывает ошибку."""
        with pytest.raises(ValueError, match="ttl must be greater than 0"):
            TTLTracker(0)

    def test_ttl_tracker_not_expired_without_touch(self):
        """Без активации TTL не должен считаться истёкшим."""
        tracker = TTLTracker(1)
        assert tracker.is_expired() is False

    def test_ttl_tracker_clear(self):
        """Очистка сбрасывает дедлайн."""
        tracker = TTLTracker(1)
        tracker.touch()
        tracker.clear()
        assert tracker.is_expired() is False

    @pytest.mark.asyncio
    async def test_ttl_tracker_expires_after_touch(self):
        """После touch TTL должен истечь по времени."""
        tracker = TTLTracker(0.01)
        tracker.touch()
        await asyncio.sleep(0.02)
        assert tracker.is_expired() is True


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

    def test_context_init_with_ttl(self):
        """TTL сохраняется в контексте."""
        context = MemoryContext(chat_id=12345, user_id=67890, ttl=60)
        assert context.ttl == 60

    def test_context_init_with_invalid_ttl(self):
        """Некорректный TTL вызывает ошибку."""
        with pytest.raises(ValueError, match="ttl must be greater than 0"):
            MemoryContext(chat_id=12345, user_id=67890, ttl=0)

    @pytest.mark.asyncio
    async def test_context_ttl_expires_data_and_state(self):
        """Просроченный контекст автоматически очищается."""
        context = MemoryContext(chat_id=12345, user_id=67890, ttl=0.01)

        await context.set_data({"name": "Max"})
        await context.set_state("waiting")
        await asyncio.sleep(0.02)

        assert await context.get_data() == {}
        assert await context.get_state() is None

    @pytest.mark.asyncio
    async def test_context_ttl_refreshes_on_activity(self):
        """Любая активность продлевает TTL контекста."""
        context = MemoryContext(chat_id=12345, user_id=67890, ttl=0.03)

        await context.set_data({"step": 1})
        await asyncio.sleep(0.02)
        assert await context.get_data() == {"step": 1}

        await asyncio.sleep(0.02)
        assert await context.get_data() == {"step": 1}

    @pytest.mark.asyncio
    async def test_set_state_none_keeps_data_until_ttl_expires(self):
        """Сброс state не должен сразу очищать data."""
        context = MemoryContext(chat_id=12345, user_id=67890, ttl=0.01)

        await context.set_data({"name": "Max"})
        await context.set_state("waiting")
        await context.set_state(None)

        assert await context.get_state() is None
        assert await context.get_data() == {"name": "Max"}

    @pytest.mark.asyncio
    async def test_set_data_after_ttl_expiration_clears_old_state(self):
        """После TTL новый set_data не должен сохранять старый state."""
        context = MemoryContext(chat_id=12345, user_id=67890, ttl=0.01)

        await context.set_data({"old": 1})
        await context.set_state("waiting")
        await asyncio.sleep(0.02)
        await context.set_data({"new": 2})

        assert await context.get_state() is None
        assert await context.get_data() == {"new": 2}


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
