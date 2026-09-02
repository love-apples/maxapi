"""Тесты фоновых задач вебхука при ``use_create_task=True``.

Задача, запущенная из ``_dispatch``, должна храниться в пуле диспетчера:
``asyncio.create_task`` не владеет задачей, и без сильной ссылки сборщик
мусора может забрать её до завершения обработки события. Пул также позволяет
дождаться обработки при остановке приложения.
"""

import asyncio
import gc

import maxapi.webhook.base as base_module
import pytest
from maxapi import Dispatcher
from maxapi.webhook.aiohttp import AiohttpMaxWebhook


class DummyBot:
    pass


class DummyEvent:
    update_type = "MESSAGE_CREATED"

    def get_ids(self):
        return (123, 456)


@pytest.fixture
def event(monkeypatch):
    """process_update_webhook всегда отдаёт готовое событие."""
    dummy = DummyEvent()

    async def fake_process(event_json, bot):
        return dummy

    monkeypatch.setattr(base_module, "process_update_webhook", fake_process)
    return dummy


def _make_webhook(dp):
    return AiohttpMaxWebhook(dp=dp, bot=DummyBot(), secret=None)


async def test_dispatch_keeps_reference_to_background_task(event):
    """Задача остаётся в пуле, пока обработка не завершилась."""
    dp = Dispatcher(use_create_task=True)
    release = asyncio.Event()

    async def slow_handle(event_object):
        await release.wait()

    dp.handle = slow_handle
    webhook = _make_webhook(dp)

    assert await webhook._dispatch({"update_type": "message_created"}) is True
    assert len(webhook._background_tasks) == 1

    # Сборка мусора не должна забрать задачу: ссылка на неё есть в пуле.
    gc.collect()
    assert len(webhook._background_tasks) == 1

    release.set()
    await webhook._shutdown()
    assert webhook._background_tasks == set()


async def test_shutdown_waits_for_running_handlers(event):
    """_shutdown() дожидается уже принятых обновлений."""
    dp = Dispatcher(use_create_task=True)
    finished = []

    async def slow_handle(event_object):
        await asyncio.sleep(0.01)
        finished.append(event_object)

    dp.handle = slow_handle
    webhook = _make_webhook(dp)

    for _ in range(3):
        await webhook._dispatch({"update_type": "message_created"})

    await webhook._shutdown()
    assert len(finished) == 3
    assert webhook._background_tasks == set()


async def test_failed_background_task_is_logged_and_released(event, caplog):
    """Упавшая задача не остаётся в пуле и её исключение не теряется."""
    dp = Dispatcher(use_create_task=True)

    async def failing_handle(event_object):
        raise RuntimeError("обработчик упал")

    dp.handle = failing_handle
    webhook = _make_webhook(dp)

    with caplog.at_level("ERROR"):
        await webhook._dispatch({"update_type": "message_created"})
        await webhook._shutdown()

    assert webhook._background_tasks == set()
    assert "обработчик упал" in caplog.text


async def test_dispatch_awaits_handler_without_create_task(event):
    """use_create_task=False: обработка идёт внутри запроса, как раньше."""
    dp = Dispatcher()
    handled = []

    async def handle(event_object):
        handled.append(event_object)

    dp.handle = handle
    webhook = _make_webhook(dp)

    await webhook._dispatch({"update_type": "message_created"})
    assert handled == [event]
    assert webhook._background_tasks == set()
