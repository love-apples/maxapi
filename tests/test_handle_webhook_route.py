import pytest

pytest.importorskip("fastapi")


import maxapi.dispatcher as dispatcher_module
from fastapi import Request
from fastapi.testclient import TestClient
from maxapi.dispatcher import Dispatcher
from maxapi.types.updates import UNKNOWN_UPDATE_DISCLAIMER


async def test_handle_webhook_unknown_update_logs_and_returns_ok(
    monkeypatch, caplog
):
    """Если process_update_webhook вернул None, ручка должна
    залогировать предупреждение и вернуть {'ok': True} с кодом 200.
    При этом dp.handle вызываться не должен.
    """
    # Подготовка диспетчера
    dp = Dispatcher()

    # Подменяем init_serve, чтобы не запускать uvicorn
    async def fake_init_serve(*args, **kwargs):
        return None

    dp.init_serve = fake_init_serve

    # Отмечаем, что uvicorn доступен для обхода проверки
    monkeypatch.setattr(dispatcher_module, "UVICORN_INSTALLED", True)

    # Гарантируем наличие Request в модуле dispatcher
    monkeypatch.setattr(dispatcher_module, "Request", Request, raising=False)

    # Подменяем парсер webhook, чтобы он возвращал None
    async def fake_process_update_webhook(event_json, bot):
        return None

    monkeypatch.setattr(
        dispatcher_module,
        "process_update_webhook",
        fake_process_update_webhook,
    )

    # Подменяем dp.handle, чтобы отследить вызовы
    called = False

    async def fake_handle(event_object):
        nonlocal called
        called = True

    dp.handle = fake_handle

    # Регистрируем ручку через handle_webhook
    class DummyBot:
        pass

    await dp.handle_webhook(bot=DummyBot())

    client = TestClient(dp.webhook_app)

    payload = {"update_type": "SOME_UNKNOWN"}
    caplog.clear()
    resp = client.post("/", json=payload)

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    # Проверяем, что в логах присутствует ожидаемое сообщение
    expected_msg = UNKNOWN_UPDATE_DISCLAIMER.format(
        update_type=payload.get("update_type")
    )
    found = any(expected_msg in rec.getMessage() for rec in caplog.records)
    assert found
    assert called is False


class DummyEvent:
    def __init__(self, update_type="MESSAGE_CREATED"):
        self.update_type = update_type

    def get_ids(self):
        return (123, 456)


async def test_handle_webhook_with_event_calls_handle_and_returns_ok(
    monkeypatch,
):
    """Если process_update_webhook вернул объект события, ручка должна
    вызвать dp.handle и вернуть {'ok': True} с кодом 200.
    """
    dp = Dispatcher()

    async def fake_init_serve(*args, **kwargs):
        return None

    dp.init_serve = fake_init_serve

    monkeypatch.setattr(dispatcher_module, "UVICORN_INSTALLED", True)

    # Гарантируем наличие Request в модуле dispatcher
    monkeypatch.setattr(dispatcher_module, "Request", Request, raising=False)

    # Создаём объект события для возврата парсером
    event = DummyEvent(update_type="MESSAGE_CREATED")

    async def fake_process_update_webhook(event_json, bot):
        return event

    monkeypatch.setattr(
        dispatcher_module,
        "process_update_webhook",
        fake_process_update_webhook,
    )

    handled = {}

    async def fake_handle(event_object):
        # Сохраняем объект для последующей проверки
        handled["obj"] = event_object

    dp.handle = fake_handle

    class DummyBot:
        pass

    await dp.handle_webhook(bot=DummyBot())

    client = TestClient(dp.webhook_app)

    payload = {"update_type": "MESSAGE_CREATED", "payload": {"x": 1}}
    resp = client.post("/", json=payload)

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    # проверяем, что обработчик был вызван нашим объектом
    assert handled.get("obj") is event
