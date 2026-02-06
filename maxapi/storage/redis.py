"""
Код файла основан на коде из проекта aiogram (лицензия MIT).
Оригинальный источник: https://github.com/aiogram/aiogram/blob/dev-3.x/aiogram/fsm/storage/redis.py
"""

import json
from collections.abc import Callable
from typing import Any, Literal, cast

from redis.asyncio.client import Redis
from redis.asyncio.connection import ConnectionPool
from redis.typing import ExpiryT

from ..context.state_machine import State


from .base import BaseStorage, StorageKey

DEFAULT_REDIS_LOCK_KWARGS = {"timeout": 60}
_JsonLoads = Callable[..., Any]
_JsonDumps = Callable[..., str]
_KeyBuilderPartType = Literal["data", "state", "lock"] | None
_KeyBuilder = Callable[[StorageKey, _KeyBuilderPartType], str]


def default_key_builder(
    key: StorageKey,
    part: Literal["data", "state", "lock"] | None = None,
) -> str:
    parts = [str(k) for k in key]

    if part:
        parts.append(part)

    return ":".join(parts)


class RedisStorage(BaseStorage):
    """
    Требуется установка пакета :code:`redis` (:code:`pip install redis`)
    """

    def __init__(
        self,
        redis: Redis,
        state_ttl: ExpiryT | None = None,
        data_ttl: ExpiryT | None = None,
        key_builder: _KeyBuilder = default_key_builder,
        json_loads: _JsonLoads = json.loads,
        json_dumps: _JsonDumps = json.dumps,
    ) -> None:
        """
        Args:
            redis (Redis): Экземпляр соединения :code:`Redis`
            key_builder (_KeyBuilder): Функция преобразования :code:`StorageKey` в строку
            state_ttl (ExpiryT): Время жизни для состояния
            data_ttl (ExpiryT): Время жизни для данных
        """
        self.redis = redis
        self.state_ttl = state_ttl
        self.data_ttl = data_ttl
        self.key_builder = key_builder
        self.json_loads = json_loads
        self.json_dumps = json_dumps

    @classmethod
    def from_url(
        cls,
        url: str,
        connection_kwargs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> "RedisStorage":
        """
        Создайте экземпляр :class:`RedisStorage` с указанием строки подключения

        Args:
            url (str): Например :code:`redis://user:password@host:port/db`
            connection_kwargs (dict[str, Any]): Смотрите документацию :code:`redis`
            **kwargs (Any): Аргументы передаваемые в :class:`RedisStorage`

        Returns:
            RedisStorage: Экземпляр :class:`RedisStorage`
        """
        if connection_kwargs is None:
            connection_kwargs = {}
        pool = ConnectionPool.from_url(url, **connection_kwargs)
        redis = Redis(connection_pool=pool)
        return cls(redis=redis, **kwargs)

    async def close(self) -> None:
        await self.redis.aclose(close_connection_pool=True)

    async def set_state(
        self,
        key: StorageKey,
        state: State | str | None = None,
    ) -> None:
        redis_key = self.key_builder(key, "state")
        if state is None:
            await self.redis.delete(redis_key)
        else:
            await self.redis.set(
                redis_key,
                cast(str, state.name if isinstance(state, State) else state),
                ex=self.state_ttl,
            )

    async def get_state(
        self,
        key: StorageKey,
    ) -> str | None:
        redis_key = self.key_builder(key, "state")
        value = await self.redis.get(redis_key)
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return cast(str | None, value)

    async def set_data(
        self,
        key: StorageKey,
        data: dict[str, Any],
    ) -> None:
        if not data:
            await self.clear(key)
            return

        redis_key = self.key_builder(key, "data")
        await self.redis.set(
            redis_key,
            self.json_dumps(data),
            ex=self.data_ttl,
        )

    async def get_data(
        self,
        key: StorageKey,
    ) -> dict[str, Any]:
        redis_key = self.key_builder(key, "data")
        value = await self.redis.get(redis_key)
        if value is None:
            return {}
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return cast(dict[str, Any], self.json_loads(value))

    async def update_data(self, key: StorageKey, **kwargs: Any) -> None:
        redis_key = self.key_builder(key, "data")
        value = await self.redis.get(redis_key)
        if value is None:
            value = {}
        else:
            value = value.decode("utf-8")
            value = cast(dict[str, Any], self.json_loads(value))

        value.update(kwargs)
        await self.redis.set(
            redis_key,
            self.json_dumps(value),
            ex=self.data_ttl,
        )

    async def clear(self, key: StorageKey) -> None:
        for part in ("data", "state"):
            redis_key = self.key_builder(key, part)
            await self.redis.delete(redis_key)
