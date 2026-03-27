from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .context import MemoryContext, RedisContext

if TYPE_CHECKING:
    from collections.abc import Callable

    from .base import BaseContext


class BaseStorage(ABC):
    """Абстракция для получения и управления контекстами."""

    @abstractmethod
    def get_context(
        self, chat_id: int | None, user_id: int | None
    ) -> BaseContext:
        """Вернуть контекст для указанной пары chat_id/user_id."""

    async def drop_context(
        self, chat_id: int | None, user_id: int | None
    ) -> None:
        """Удалить контекст из хранилища, если он существует."""
        return None

    async def cleanup(self) -> None:
        """Очистить устаревшие элементы хранилища."""
        return None

    async def close(self) -> None:
        """Завершить работу хранилища и освободить ресурсы."""
        return None

    def get_cached_contexts(
        self,
    ) -> dict[tuple[int | None, int | None], BaseContext]:
        """Вернуть текущий in-memory view контекстов, если он есть."""
        return {}


@dataclass(slots=True)
class _ContextEntry:
    context: BaseContext
    last_access_monotonic: float


class MemoryStorage(BaseStorage):
    """In-memory storage с TTL и ограничением размера."""

    def __init__(
        self,
        *,
        context_ttl: float | None = 3600.0,
        max_contexts: int | None = 10000,
        cleanup_interval: float = 60.0,
        context_factory: Callable[..., BaseContext] = MemoryContext,
        **context_kwargs: Any,
    ) -> None:
        self.context_ttl = context_ttl
        self.max_contexts = max_contexts
        self.cleanup_interval = cleanup_interval
        self.context_factory = context_factory
        self.context_kwargs = context_kwargs
        self._entries: dict[tuple[int | None, int | None], _ContextEntry] = {}
        self._last_cleanup_monotonic = time.monotonic()

    def get_context(
        self, chat_id: int | None, user_id: int | None
    ) -> BaseContext:
        self._maybe_cleanup()

        key = (chat_id, user_id)
        now = time.monotonic()
        entry = self._entries.get(key)

        if entry is None:
            entry = _ContextEntry(
                context=self.context_factory(
                    chat_id, user_id, **self.context_kwargs
                ),
                last_access_monotonic=now,
            )
            self._entries[key] = entry
            self._enforce_limit()
            return entry.context

        entry.last_access_monotonic = now
        return entry.context

    async def drop_context(
        self, chat_id: int | None, user_id: int | None
    ) -> None:
        self._entries.pop((chat_id, user_id), None)

    async def cleanup(self) -> None:
        self._cleanup_now()

    def _cleanup_now(self) -> None:
        now = time.monotonic()

        if self.context_ttl is not None:
            expired_keys = [
                key
                for key, entry in self._entries.items()
                if now - entry.last_access_monotonic > self.context_ttl
            ]
            for key in expired_keys:
                self._entries.pop(key, None)

        self._enforce_limit()
        self._last_cleanup_monotonic = now

    async def close(self) -> None:
        self._entries.clear()

    def get_cached_contexts(
        self,
    ) -> dict[tuple[int | None, int | None], BaseContext]:
        return {key: entry.context for key, entry in self._entries.items()}

    def _maybe_cleanup(self) -> None:
        if self.cleanup_interval <= 0:
            return

        now = time.monotonic()
        if now - self._last_cleanup_monotonic >= self.cleanup_interval:
            self._cleanup_now()

    def _enforce_limit(self) -> None:
        if (
            self.max_contexts is None
            or len(self._entries) <= self.max_contexts
        ):
            return

        overflow = len(self._entries) - self.max_contexts
        oldest_keys = sorted(
            self._entries,
            key=lambda key: self._entries[key].last_access_monotonic,
        )[:overflow]
        for key in oldest_keys:
            self._entries.pop(key, None)


class RedisStorage(BaseStorage):
    """Storage для Redis-контекстов без локального бесконечного кэша."""

    def __init__(
        self,
        redis_client: Any,
        *,
        key_prefix: str = "maxapi",
        state_ttl: int | None = None,
        data_ttl: int | None = None,
    ) -> None:
        self.redis_client = redis_client
        self.key_prefix = key_prefix
        self.state_ttl = state_ttl
        self.data_ttl = data_ttl

    def get_context(
        self, chat_id: int | None, user_id: int | None
    ) -> BaseContext:
        return RedisContext(
            chat_id=chat_id,
            user_id=user_id,
            redis_client=self.redis_client,
            key_prefix=self.key_prefix,
            state_ttl=self.state_ttl,
            data_ttl=self.data_ttl,
        )

    def get_cached_contexts(
        self,
    ) -> dict[tuple[int | None, int | None], BaseContext]:
        return {}


class LegacyContextStorageAdapter(BaseStorage):
    """Адаптер для старого API Dispatcher(storage=MemoryContext, ...)."""

    def __init__(self, context_cls: type[BaseContext], **context_kwargs: Any):
        self._storage = MemoryStorage(
            context_factory=context_cls,
            context_ttl=None,
            max_contexts=None,
            cleanup_interval=0,
            **context_kwargs,
        )

    def get_context(
        self, chat_id: int | None, user_id: int | None
    ) -> BaseContext:
        return self._storage.get_context(chat_id, user_id)

    async def drop_context(
        self, chat_id: int | None, user_id: int | None
    ) -> None:
        await self._storage.drop_context(chat_id, user_id)

    async def cleanup(self) -> None:
        await self._storage.cleanup()

    async def close(self) -> None:
        await self._storage.close()

    def get_cached_contexts(
        self,
    ) -> dict[tuple[int | None, int | None], BaseContext]:
        return self._storage.get_cached_contexts()
