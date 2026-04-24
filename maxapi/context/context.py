import asyncio
import json
from typing import Any

from ..context.base import BaseContext
from ..context.state_machine import State


def _ttl_to_ms(ttl: float | None) -> int | None:
    if ttl is None:
        return None
    return max(1, round(ttl * 1000))


class MemoryContext(BaseContext):
    """
    Контекст хранения данных пользователя в оперативной памяти.
    """

    def __init__(
        self, chat_id: int | None, user_id: int | None, **kwargs: Any
    ) -> None:
        super().__init__(chat_id, user_id, **kwargs)
        self._context: dict[str, Any] = {}
        self._state: State | str | None = None
        self._lock = asyncio.Lock()

    async def get_data(self) -> dict[str, Any]:
        """
        Возвращает текущий контекст данных.

        Returns:
            Словарь с данными контекста
        """

        async with self._lock:
            await self._expire_if_needed()
            self._ttl_tracker.touch()
            return self._context.copy()

    async def set_data(self, data: dict[str, Any]) -> None:
        """
        Полностью заменяет контекст данных.

        Args:
            data: Новый словарь контекста
        """

        async with self._lock:
            await self._expire_if_needed()
            self._context = data
            self._ttl_tracker.touch()

    async def update_data(self, **kwargs: Any) -> None:
        """
        Обновляет контекст данных новыми значениями.

        Args:
            **kwargs: Пары ключ-значение для обновления
        """

        async with self._lock:
            await self._expire_if_needed()
            self._context.update(kwargs)
            self._ttl_tracker.touch()

    async def set_state(self, state: State | str | None = None) -> None:
        """
        Устанавливает новое состояние.

        Args:
            state: Новое состояние или None для сброса
        """

        async with self._lock:
            await self._expire_if_needed()
            self._state = state
            self._ttl_tracker.touch()

    async def get_state(self) -> State | str | None:
        """
        Возвращает текущее состояние.

        Returns:
            Текущее состояние или None
        """

        async with self._lock:
            await self._expire_if_needed()
            self._ttl_tracker.touch()
            return self._state

    async def clear(self) -> None:
        """
        Очищает контекст и сбрасывает состояние.
        """

        async with self._lock:
            self._state = None
            self._context = {}
            self._ttl_tracker.clear()

    async def _expire_if_needed(self) -> None:
        """Очищает контекст, если его TTL истёк."""
        if self._ttl_tracker.is_expired():
            self._state = None
            self._context = {}
            self._ttl_tracker.clear()


class RedisContext(BaseContext):
    """
    Контекст хранения данных пользователя в Redis.
    Требует установленной библиотеки redis: pip install redis
    """

    def __init__(
        self,
        chat_id: int | None,
        user_id: int | None,
        redis_client: Any,  # redis.asyncio.Redis
        key_prefix: str = "maxapi",
        **kwargs: Any,
    ) -> None:
        super().__init__(chat_id, user_id, **kwargs)
        self.redis = redis_client
        self.prefix = f"{key_prefix}:{chat_id}:{user_id}"
        self.data_key = f"{self.prefix}:data"
        self.state_key = f"{self.prefix}:state"

    async def get_data(self) -> dict[str, Any]:
        data = await self.redis.get(self.data_key)
        await self._touch_redis_ttl()
        return json.loads(data) if data else {}

    async def set_data(self, data: dict[str, Any]) -> None:
        ttl_ms = _ttl_to_ms(self.ttl)
        payload = json.dumps(data)
        if ttl_ms is None:
            await self.redis.set(self.data_key, payload)
        else:
            await self.redis.set(self.data_key, payload, px=ttl_ms)
            await self.redis.pexpire(self.state_key, ttl_ms)

    async def update_data(self, **kwargs: Any) -> None:
        """
        Атомарно обновляет данные
        """
        lua_script = """
        local data = redis.call('get', KEYS[1])
        local decoded = {}
        if data then
            decoded = cjson.decode(data)
        end
        local updates = cjson.decode(ARGV[1])
        for k, v in pairs(updates) do
            decoded[k] = v
        end
        if ARGV[2] then
            redis.call('set', KEYS[1], cjson.encode(decoded), 'PX', ARGV[2])
        else
            redis.call('set', KEYS[1], cjson.encode(decoded))
        end
        return redis.status_reply("OK")
        """
        ttl_ms = _ttl_to_ms(self.ttl)
        await self.redis.eval(
            lua_script,
            1,
            self.data_key,
            json.dumps(kwargs),
            str(ttl_ms) if ttl_ms is not None else "",
        )
        if ttl_ms is not None:
            await self.redis.pexpire(self.state_key, ttl_ms)

    async def set_state(self, state: State | str | None = None) -> None:
        if state is None:
            await self.redis.delete(self.state_key)
        else:
            # Сохраняем имя состояния, если это объект State
            state_val = state.name if isinstance(state, State) else state
            await self.redis.set(self.state_key, str(state_val))
        await self._touch_redis_ttl()

    async def get_state(self) -> State | str | None:
        state = await self.redis.get(self.state_key)
        await self._touch_redis_ttl()
        if isinstance(state, bytes):
            return state.decode("utf-8")
        return state

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def clear(self) -> None:
        await self.redis.delete(self.data_key, self.state_key)
        self._ttl_tracker.clear()

    async def _touch_redis_ttl(self) -> None:
        """Продлевает TTL обоих ключей контекста при активности."""
        ttl_ms = _ttl_to_ms(self.ttl)
        if ttl_ms is None:
            return
        await self.redis.pexpire(self.data_key, ttl_ms)
        await self.redis.pexpire(self.state_key, ttl_ms)
