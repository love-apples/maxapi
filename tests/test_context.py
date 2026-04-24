"""Тесты для Context и State Machine."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from maxapi.context import MemoryContext, RedisContext
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
        with pytest.raises(
            ValueError, match="ttl must be a positive finite number"
        ):
            TTLTracker(0)

    @pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
    def test_ttl_tracker_init_rejects_non_finite_or_negative(self, value):
        """TTL должен быть положительным конечным числом."""
        with pytest.raises(
            ValueError, match="ttl must be a positive finite number"
        ):
            TTLTracker(value)

    def test_ttl_tracker_touch_without_ttl_keeps_no_deadline(self):
        """Без TTL touch не создаёт дедлайн."""
        tracker = TTLTracker(None)
        tracker.touch()
        assert tracker.is_expired() is False
        assert tracker._expires_at is None

    def test_ttl_tracker_clear(self):
        """Очистка сбрасывает дедлайн."""
        tracker = TTLTracker(1)
        tracker.touch()
        tracker.clear()
        assert tracker.is_expired() is False

    def test_ttl_tracker_expires_after_touch(self):
        """После touch TTL должен истечь по времени."""
        current_time = {"value": 100.0}

        with patch(
            "maxapi.context.ttl.monotonic",
            side_effect=lambda: current_time["value"],
        ):
            tracker = TTLTracker(0.01)
            tracker.touch()
            current_time["value"] = 100.02
            assert tracker.is_expired() is True

    def test_ttl_tracker_rounds_small_ttl_to_one_ms(self):
        """Очень маленький TTL в Redis должен округляться до 1ms."""
        from maxapi.context.context import _ttl_to_ms

        assert _ttl_to_ms(0.0001) == 1


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

    async def test_get_data_empty(self, sample_context):
        """Тест получения пустых данных."""
        data = await sample_context.get_data()
        assert data == {}

    async def test_set_data(self, sample_context):
        """Тест установки данных."""
        test_data = {"key1": "value1", "key2": 42}
        await sample_context.set_data(test_data)

        data = await sample_context.get_data()
        assert data == test_data

    async def test_update_data(self, sample_context):
        """Тест обновления данных."""
        await sample_context.set_data({"key1": "value1"})
        await sample_context.update_data(key2="value2", key3=123)

        data = await sample_context.get_data()
        assert data["key1"] == "value1"
        assert data["key2"] == "value2"
        assert data["key3"] == 123

    async def test_get_state_none(self, sample_context):
        """Тест получения состояния (изначально None)."""
        state = await sample_context.get_state()
        assert state is None

    async def test_set_state_string(self, sample_context):
        """Тест установки строкового состояния."""
        await sample_context.set_state("test_state")
        state = await sample_context.get_state()
        assert state == "test_state"

    async def test_set_state_none(self, sample_context):
        """Тест сброса состояния."""
        await sample_context.set_state("test_state")
        await sample_context.set_state(None)
        state = await sample_context.get_state()
        assert state is None

    async def test_clear(self, sample_context):
        """Тест очистки контекста."""
        await sample_context.set_data({"key": "value"})
        await sample_context.set_state("test_state")

        await sample_context.clear()

        data = await sample_context.get_data()
        state = await sample_context.get_state()

        assert data == {}
        assert state is None

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
        with pytest.raises(
            ValueError, match="ttl must be a positive finite number"
        ):
            MemoryContext(chat_id=12345, user_id=67890, ttl=0)

    async def test_context_ttl_expires_data_and_state(self):
        """Просроченный контекст автоматически очищается."""
        current_time = {"value": 0.0}
        with patch(
            "maxapi.context.ttl.monotonic",
            side_effect=lambda: current_time["value"],
        ):
            context = MemoryContext(chat_id=12345, user_id=67890, ttl=0.01)
            await context.set_data({"name": "Max"})
            await context.set_state("waiting")
            current_time["value"] = 0.02

            assert await context.get_data() == {}
            assert await context.get_state() is None

    async def test_context_ttl_refreshes_on_activity(self):
        """Любая активность продлевает TTL контекста."""
        current_time = {"value": 0.0}
        with patch(
            "maxapi.context.ttl.monotonic",
            side_effect=lambda: current_time["value"],
        ):
            context = MemoryContext(chat_id=12345, user_id=67890, ttl=0.03)

            await context.set_data({"step": 1})
            current_time["value"] = 0.02
            assert await context.get_data() == {"step": 1}

            current_time["value"] = 0.04
            assert await context.get_data() == {"step": 1}

    async def test_set_state_none_keeps_data_until_ttl_expires(self):
        """Сброс state не должен сразу очищать data."""
        context = MemoryContext(chat_id=12345, user_id=67890, ttl=0.01)

        await context.set_data({"name": "Max"})
        await context.set_state("waiting")
        await context.set_state(None)

        assert await context.get_state() is None
        assert await context.get_data() == {"name": "Max"}

    async def test_set_data_after_ttl_expiration_clears_old_state(self):
        """После TTL новый set_data не должен сохранять старый state."""
        current_time = {"value": 0.0}
        with patch(
            "maxapi.context.ttl.monotonic",
            side_effect=lambda: current_time["value"],
        ):
            context = MemoryContext(chat_id=12345, user_id=67890, ttl=0.01)

            await context.set_data({"old": 1})
            await context.set_state("waiting")
            current_time["value"] = 0.02
            await context.set_data({"new": 2})

            assert await context.get_state() is None
            assert await context.get_data() == {"new": 2}


class TestRedisContext:
    """Тесты RedisContext."""

    def test_redis_context_init(self):
        """Контекст корректно собирает redis-ключи."""
        redis = AsyncMock()
        context = RedisContext(
            chat_id=12345,
            user_id=67890,
            redis_client=redis,
            key_prefix="test_bot",
        )

        assert context.redis is redis
        assert context.prefix == "test_bot:12345:67890"
        assert context.data_key == "test_bot:12345:67890:data"
        assert context.state_key == "test_bot:12345:67890:state"

    async def test_redis_get_data_empty_without_ttl(self):
        """Пустые данные из Redis возвращаются как пустой словарь."""
        redis = AsyncMock()
        redis.get.return_value = None
        context = RedisContext(chat_id=1, user_id=2, redis_client=redis)

        data = await context.get_data()

        assert data == {}
        redis.get.assert_awaited_once_with(context.data_key)
        redis.pexpire.assert_not_awaited()

    async def test_redis_get_data_refreshes_ttl(self):
        """При чтении данные декодируются и TTL продлевается."""
        redis = AsyncMock()
        redis.get.return_value = json.dumps({"food": "mint"})
        context = RedisContext(
            chat_id=1,
            user_id=2,
            redis_client=redis,
            ttl=0.5,
        )

        data = await context.get_data()

        assert data == {"food": "mint"}
        redis.pexpire.assert_any_await(context.data_key, 500)
        redis.pexpire.assert_any_await(context.state_key, 500)

    async def test_redis_set_data(self):
        """set_data сериализует словарь в JSON."""
        redis = AsyncMock()
        context = RedisContext(chat_id=1, user_id=2, redis_client=redis)

        await context.set_data({"food": "cucumber"})

        redis.set.assert_awaited_once_with(
            context.data_key, json.dumps({"food": "cucumber"})
        )

    async def test_redis_set_data_sets_ttl_atomically(self):
        """set_data должен выставлять TTL для data-key в том же SET."""
        redis = AsyncMock()
        context = RedisContext(
            chat_id=1,
            user_id=2,
            redis_client=redis,
            ttl=0.5,
        )

        await context.set_data({"food": "cucumber"})

        redis.set.assert_awaited_once_with(
            context.data_key,
            json.dumps({"food": "cucumber"}),
            px=500,
        )
        redis.pexpire.assert_awaited_once_with(context.state_key, 500)

    async def test_redis_update_data(self):
        """update_data вызывает Lua-обновление и продлевает TTL."""
        redis = AsyncMock()
        context = RedisContext(
            chat_id=1,
            user_id=2,
            redis_client=redis,
            ttl=1.25,
        )

        await context.update_data(food="mint", city="Samara")

        redis.eval.assert_awaited_once()
        _, keys_count, key, payload, ttl_ms = redis.eval.await_args.args
        assert keys_count == 1
        assert key == context.data_key
        assert json.loads(payload) == {"food": "mint", "city": "Samara"}
        assert ttl_ms == "1250"
        redis.pexpire.assert_awaited_once_with(context.state_key, 1250)

    async def test_redis_set_state_none(self):
        """set_state(None) удаляет ключ состояния."""
        redis = AsyncMock()
        context = RedisContext(chat_id=1, user_id=2, redis_client=redis)

        await context.set_state(None)

        redis.delete.assert_awaited_once_with(context.state_key)

    async def test_redis_set_state_object(self):
        """State-объект сохраняется по его имени."""

        class Form(StatesGroup):
            waiting = State()

        redis = AsyncMock()
        context = RedisContext(chat_id=1, user_id=2, redis_client=redis)

        await context.set_state(Form.waiting)

        redis.set.assert_awaited_once_with(context.state_key, "Form:waiting")

    async def test_redis_get_state_decodes_bytes(self):
        """Байты из Redis декодируются в строку."""
        redis = AsyncMock()
        redis.get.return_value = b"waiting"
        context = RedisContext(chat_id=1, user_id=2, redis_client=redis)

        state = await context.get_state()

        assert state == "waiting"

    async def test_redis_get_state_returns_plain_value(self):
        """Строковое состояние возвращается без декодирования."""
        redis = AsyncMock()
        redis.get.return_value = "processing"
        context = RedisContext(chat_id=1, user_id=2, redis_client=redis)

        state = await context.get_state()

        assert state == "processing"

    async def test_redis_context_manager_and_clear(self):
        """Контекстный менеджер и clear работают без побочных эффектов."""
        redis = AsyncMock()
        context = RedisContext(chat_id=1, user_id=2, redis_client=redis, ttl=1)
        context.touch_ttl()

        entered = await context.__aenter__()
        await context.__aexit__(None, None, None)
        await context.clear()

        assert entered is context
        redis.delete.assert_awaited_once_with(
            context.data_key, context.state_key
        )
        assert context.is_ttl_expired() is False


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
