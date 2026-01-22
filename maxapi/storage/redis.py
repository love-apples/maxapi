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
    Требуется установка Redis :code:`redis` package installed (:code:`pip install redis`)
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
        :param redis: экземпляр соединения Redis
        :param key_builder: функция преобразования StorageKey в строку
        :param state_ttl: время жизни для состояния
        :param data_ttl: время жизни для данных
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

        :param url: например :code:`redis://user:password@host:port/db`
        :param connection_kwargs: смотрите документацию :code:`redis`
        :param kwargs: аргументы передаваемые в :class:`RedisStorage`
        :return: экземпляр :class:`RedisStorage`
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
        redis_key = self.key_builder(key, "data")
        if not data:
            await self.redis.delete(redis_key)
            return
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
