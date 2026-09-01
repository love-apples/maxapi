# Портировано и адаптировано из aiogram
# (https://github.com/aiogram/aiogram, aiogram/fsm/storage/).
#
# MIT License
#
# Copyright (c) 2017 - present Alex Root Junior
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""
Изоляция обработки событий (аналог ``EventIsolation`` из aiogram).

Сериализует конкурентную обработку апдейтов одного пользователя,
чтобы FSM-переход, завершённый предыдущим апдейтом, был виден
следующему. Без изоляции при параллельной обработке
(``Dispatcher(use_create_task=True)`` или вебхук) два быстрых
сообщения одного пользователя читают один и тот же снимок состояния
и одноразовый шаг FSM выполняется дважды.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from asyncio import Lock
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from contextlib import AbstractAsyncContextManager

IsolationKey = tuple[int | None, int | None]
"""Ключ изоляции: ``(chat_id, user_id)``."""

DEFAULT_REDIS_LOCK_TIMEOUT: float = 60.0
DEFAULT_REDIS_LOCK_SLEEP: float = 0.1


class BaseEventIsolation(ABC):
    """
    Базовый класс изоляции обработки событий.

    Реализация обязана вернуть асинхронный контекст-менеджер,
    удерживающий блокировку по ключу ``(chat_id, user_id)`` на всё
    время обработки события.
    """

    @abstractmethod
    def lock(self, key: IsolationKey) -> AbstractAsyncContextManager[None]:
        """
        Возвращает контекст-менеджер блокировки по ключу.

        Args:
            key: Ключ изоляции ``(chat_id, user_id)``.
        """

    @abstractmethod
    async def close(self) -> None:
        """Освобождает ресурсы изоляции."""


class DisabledEventIsolation(BaseEventIsolation):
    """
    Отключённая изоляция (поведение по умолчанию).

    События обрабатываются без сериализации — как до появления
    механизма изоляции.
    """

    @asynccontextmanager
    async def lock(self, key: IsolationKey) -> AsyncIterator[None]:
        """No-op: блокировка не берётся."""
        yield

    async def close(self) -> None:
        """No-op."""


class SimpleEventIsolation(BaseEventIsolation):
    """
    Изоляция на ``asyncio.Lock`` в памяти процесса.

    На каждый ключ ``(chat_id, user_id)`` создаётся отдельная
    блокировка; события одного пользователя обрабатываются строго
    последовательно (в порядке поступления — ``asyncio.Lock``
    пробуждает ожидающих в FIFO), события разных пользователей —
    параллельно.

    В отличие от aiogram, неиспользуемые блокировки удаляются из
    словаря, как только их никто не держит и не ожидает.

    Подходит только для одного процесса. При нескольких процессах
    (например, вебхук за балансировщиком) используйте
    :class:`RedisEventIsolation`.
    """

    def __init__(self) -> None:
        self._locks: dict[IsolationKey, Lock] = {}
        self._refcounts: dict[IsolationKey, int] = {}

    @asynccontextmanager
    async def lock(self, key: IsolationKey) -> AsyncIterator[None]:
        """
        Удерживает блокировку по ключу на время контекста.

        Args:
            key: Ключ изоляции ``(chat_id, user_id)``.
        """
        lock = self._locks.get(key)
        if lock is None:
            lock = Lock()
            self._locks[key] = lock
        self._refcounts[key] = self._refcounts.get(key, 0) + 1
        try:
            async with lock:
                yield
        finally:
            refs = self._refcounts.get(key, 1) - 1
            if refs > 0:
                self._refcounts[key] = refs
            else:
                # Блокировку никто не держит и не ждёт — чистим,
                # чтобы словарь не рос бесконечно
                self._refcounts.pop(key, None)
                self._locks.pop(key, None)

    async def close(self) -> None:
        """Очищает словарь блокировок."""
        self._locks.clear()
        self._refcounts.clear()


class RedisEventIsolation(BaseEventIsolation):
    """
    Распределённая изоляция на блокировках Redis.

    Сериализует обработку событий одного пользователя между
    несколькими процессами/инстансами бота. Парная к
    :class:`~maxapi.context.context.RedisContext` — используйте их
    вместе. Требует установленной библиотеки redis:
    ``pip install redis``.
    """

    def __init__(
        self,
        redis_client: Any,  # redis.asyncio.Redis
        key_prefix: str = "maxapi",
        lock_timeout: float | None = DEFAULT_REDIS_LOCK_TIMEOUT,
        lock_sleep: float = DEFAULT_REDIS_LOCK_SLEEP,
    ) -> None:
        """
        Инициализация изоляции.

        Args:
            redis_client: Экземпляр ``redis.asyncio.Redis``.
            key_prefix: Префикс ключей блокировок. Должен совпадать
                с ``key_prefix`` вашего ``RedisContext``.
            lock_timeout: Максимальное время удержания блокировки в
                секундах (страховка от вечного лока при падении
                процесса). None — без ограничения.
            lock_sleep: Интервал опроса блокировки в секундах.
        """
        self.redis = redis_client
        self.key_prefix = key_prefix
        self.lock_timeout = lock_timeout
        self.lock_sleep = lock_sleep

    @asynccontextmanager
    async def lock(self, key: IsolationKey) -> AsyncIterator[None]:
        """
        Удерживает распределённую блокировку по ключу.

        Args:
            key: Ключ изоляции ``(chat_id, user_id)``.
        """
        chat_id, user_id = key
        name = f"{self.key_prefix}:{chat_id}:{user_id}:lock"
        async with self.redis.lock(
            name=name,
            timeout=self.lock_timeout,
            sleep=self.lock_sleep,
        ):
            yield

    async def close(self) -> None:
        """No-op: соединением Redis владеет вызывающая сторона."""
