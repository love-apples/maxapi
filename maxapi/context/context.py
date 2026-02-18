import asyncio
import json
from typing import Any

from ..context.base import BaseContext
from ..context.state_machine import State


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
            return self._context

    async def set_data(self, data: dict[str, Any]) -> None:
        """
        Полностью заменяет контекст данных.

        Args:
            data: Новый словарь контекста
        """

        async with self._lock:
            self._context = data

    async def update_data(self, **kwargs: Any) -> None:
        """
        Обновляет контекст данных новыми значениями.

        Args:
            **kwargs: Пары ключ-значение для обновления
        """

        async with self._lock:
            self._context.update(kwargs)

    async def set_state(self, state: State | str | None = None) -> None:
        """
        Устанавливает новое состояние.

        Args:
            state: Новое состояние или None для сброса
        """

        async with self._lock:
            self._state = state

    async def get_state(self) -> State | str | None:
        """
        Возвращает текущее состояние.

        Returns:
            Текущее состояние или None
        """

        async with self._lock:
            return self._state

    async def clear(self) -> None:
        """
        Очищает контекст и сбрасывает состояние.
        """

        async with self._lock:
            self._state = None
            self._context = {}


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
        return json.loads(data) if data else {}

    async def set_data(self, data: dict[str, Any]) -> None:
        await self.redis.set(self.data_key, json.dumps(data))

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
        redis.call('set', KEYS[1], cjson.encode(decoded))
        return redis.status_reply("OK")
        """
        await self.redis.eval(lua_script, 1, self.data_key, json.dumps(kwargs))

    async def set_state(self, state: State | str | None = None) -> None:
        if state is None:
            await self.redis.delete(self.state_key)
        else:
            # Сохраняем имя состояния, если это объект State
            state_val = state.name if isinstance(state, State) else state
            await self.redis.set(self.state_key, str(state_val))

    async def get_state(self) -> State | str | None:
        state = await self.redis.get(self.state_key)
        if isinstance(state, bytes):
            return state.decode("utf-8")
        return state

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def clear(self) -> None:
        await self.redis.delete(self.data_key, self.state_key)
