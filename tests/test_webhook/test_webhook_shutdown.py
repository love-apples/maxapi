"""Тесты shutdown-цикла webhook-интеграций.

При остановке приложения вебхук должен дождаться фоновых задач
handle() и освободить ресурсы изоляции событий.
"""

import asyncio

from maxapi import Dispatcher
from maxapi.context import SimpleEventIsolation
from maxapi.webhook.aiohttp import AiohttpMaxWebhook
from maxapi.webhook.base import BaseMaxWebhook


class DummyBot:
    pass


class _RecordingIsolation(SimpleEventIsolation):
    """Изоляция, фиксирующая вызов close()."""

    def __init__(self) -> None:
        super().__init__()
        self.closed = False

    async def close(self) -> None:
        self.closed = True
        await super().close()


def _dispatcher_with_pending_task() -> tuple[Dispatcher, list]:
    """Диспетчер с незавершённой фоновой задачей в пуле.

    Returns:
        Кортеж (dispatcher, done) — done наполняется по завершении
        задачи.
    """
    dp = Dispatcher(
        use_create_task=True,
        event_isolation=_RecordingIsolation(),
    )
    done: list = []

    async def _pending() -> None:
        await asyncio.sleep(0.01)
        done.append(True)

    task = asyncio.get_running_loop().create_task(_pending())
    dp._background_tasks.add(task)
    task.add_done_callback(dp._on_background_task_done)
    return dp, done


class TestDispatcherShutdown:
    """Тесты Dispatcher.shutdown()."""

    async def test_shutdown_waits_tasks_and_closes_isolation(self):
        """shutdown() дожидается фоновых задач и закрывает
        изоляцию."""
        dp, done = _dispatcher_with_pending_task()

        await dp.shutdown()

        assert done == [True]
        assert dp.event_isolation.closed

    async def test_shutdown_is_idempotent(self):
        """Повторный shutdown() не падает."""
        dp = Dispatcher(event_isolation=_RecordingIsolation())
        await dp.shutdown()
        await dp.shutdown()
        assert dp.event_isolation.closed

    async def test_shutdown_drains_late_added_tasks(self):
        """Задача, добавленная в пул во время drain, тоже будет
        дождана до закрытия изоляции (drain-цикл до пустого пула)."""
        dp = Dispatcher(
            use_create_task=True,
            event_isolation=_RecordingIsolation(),
        )
        done: list = []
        loop = asyncio.get_running_loop()

        async def _late() -> None:
            await asyncio.sleep(0.01)
            done.append("late")

        async def _first() -> None:
            # Пока shutdown() ждёт снимок пула с этой задачей,
            # добавляем в пул новую — как конкурентный продюсер
            late_task = loop.create_task(_late())
            dp._background_tasks.add(late_task)
            late_task.add_done_callback(dp._on_background_task_done)
            await asyncio.sleep(0.01)
            done.append("first")

        first_task = loop.create_task(_first())
        dp._background_tasks.add(first_task)
        first_task.add_done_callback(dp._on_background_task_done)

        await dp.shutdown()

        assert sorted(done) == ["first", "late"]
        assert dp._background_tasks == set()
        assert dp.event_isolation.closed

    async def test_spawn_handle_task_registers_in_pool(self, monkeypatch):
        """spawn_handle_task() регистрирует задачу в пуле и
        удаляет её по завершении."""
        dp = Dispatcher(use_create_task=True)

        async def fake_handle(event) -> None:
            await asyncio.sleep(0)

        monkeypatch.setattr(dp, "handle", fake_handle)

        task = dp.spawn_handle_task(object())
        assert task in dp._background_tasks

        await task
        # done-callback выполняется через call_soon — даём циклу
        # шанс его отработать
        await asyncio.sleep(0)
        assert dp._background_tasks == set()


class TestWebhookShutdownHooks:
    """Тесты подключения shutdown к lifecycle бэкендов."""

    async def test_base_shutdown_delegates_to_dispatcher(self):
        """BaseMaxWebhook._shutdown() вызывает dp.shutdown()."""
        dp, done = _dispatcher_with_pending_task()

        webhook = AiohttpMaxWebhook(dp=dp, bot=DummyBot(), secret="s")
        await webhook._shutdown()

        assert done == [True]
        assert dp.event_isolation.closed

    async def test_aiohttp_create_app_registers_on_cleanup(self):
        """create_app() регистрирует on_cleanup-хук aiohttp.

        Именно on_cleanup: on_shutdown срабатывает до ожидания
        активных запросов, и drain был бы преждевременным.
        """
        dp = Dispatcher(event_isolation=_RecordingIsolation())
        webhook = AiohttpMaxWebhook(dp=dp, bot=DummyBot(), secret="s")

        app = webhook.create_app(path="/hook")

        assert webhook.on_cleanup in list(app.on_cleanup)
        assert not list(app.on_shutdown)

    async def test_aiohttp_on_cleanup_closes_isolation(self):
        """on_cleanup-хук aiohttp закрывает изоляцию."""
        dp, done = _dispatcher_with_pending_task()
        webhook = AiohttpMaxWebhook(dp=dp, bot=DummyBot(), secret="s")

        await webhook.on_cleanup(app=None)

        assert done == [True]
        assert dp.event_isolation.closed

    async def test_fastapi_lifespan_shuts_down_on_exit(self, monkeypatch):
        """Выход из lifespan FastAPI дожидается задач и закрывает
        изоляцию."""
        try:
            from maxapi.webhook.fastapi import (
                FastAPIMaxWebhook,
            )
        except ImportError:
            import pytest

            pytest.skip("fastapi не установлен")

        dp, done = _dispatcher_with_pending_task()
        webhook = FastAPIMaxWebhook(dp=dp, bot=DummyBot(), secret="s")

        async def fake_startup(self) -> None:
            pass

        monkeypatch.setattr(BaseMaxWebhook, "_startup", fake_startup)

        async with webhook.lifespan(app=None):
            assert not dp.event_isolation.closed

        assert done == [True]
        assert dp.event_isolation.closed

    async def test_litestar_on_shutdown_closes_isolation(self):
        """on_shutdown-хук Litestar закрывает изоляцию."""
        try:
            from maxapi.webhook.litestar import (
                LitestarMaxWebhook,
            )
        except ImportError:
            import pytest

            pytest.skip("litestar не установлен")

        dp, done = _dispatcher_with_pending_task()
        webhook = LitestarMaxWebhook(dp=dp, bot=DummyBot(), secret="s")

        await webhook.on_shutdown()

        assert done == [True]
        assert dp.event_isolation.closed
