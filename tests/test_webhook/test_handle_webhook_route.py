import pytest

pytest.importorskip("fastapi")

import maxapi.webhook.base as integration_module
from fastapi.testclient import TestClient
from maxapi import Dispatcher
from maxapi.types.updates import UNKNOWN_UPDATE_DISCLAIMER
from maxapi.webhook.fastapi import DEFAULT_PATH, FastAPIMaxWebhook


class DummyBot:
    pass


class DummyEvent:
    def __init__(self, update_type="MESSAGE_CREATED"):
        self.update_type = update_type

    def get_ids(self):
        return (123, 456)


async def test_handle_webhook_unknown_update_logs_and_returns_ok(
    monkeypatch, caplog
):
    """Если process_update_webhook вернул None, ручка должна
    залогировать предупреждение и вернуть {'ok': True} с кодом 200.
    При этом dp.handle вызываться не должен.
    """
    dp = Dispatcher()

    async def fake_startup(bot):
        pass

    dp.startup = fake_startup

    async def fake_process_update_webhook(event_json, bot):
        return None

    monkeypatch.setattr(
        integration_module,
        "process_update_webhook",
        fake_process_update_webhook,
    )

    called = False

    async def fake_handle(event_object):
        nonlocal called
        called = True

    dp.handle = fake_handle

    webhook = FastAPIMaxWebhook(dp=dp, bot=DummyBot())
    app = webhook.create_app(path=DEFAULT_PATH)
    client = TestClient(app, raise_server_exceptions=True)

    payload = {"update_type": "SOME_UNKNOWN"}
    caplog.clear()
    resp = client.post("/", json=payload)

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    expected_msg = UNKNOWN_UPDATE_DISCLAIMER.format(
        update_type=payload.get("update_type")
    )
    found = any(expected_msg in rec.getMessage() for rec in caplog.records)
    assert found
    assert called is False


async def test_handle_webhook_with_event_calls_handle_and_returns_ok(
    monkeypatch,
):
    """Если process_update_webhook вернул объект события, ручка должна
    вызвать dp.handle и вернуть {'ok': True} с кодом 200.
    """
    dp = Dispatcher()

    async def fake_startup(bot):
        pass

    dp.startup = fake_startup

    event = DummyEvent(update_type="MESSAGE_CREATED")

    async def fake_process_update_webhook(event_json, bot):
        return event

    monkeypatch.setattr(
        integration_module,
        "process_update_webhook",
        fake_process_update_webhook,
    )

    handled = {}

    async def fake_handle(event_object):
        handled["obj"] = event_object

    dp.handle = fake_handle

    webhook = FastAPIMaxWebhook(dp=dp, bot=DummyBot())
    app = webhook.create_app(path=DEFAULT_PATH)
    client = TestClient(app, raise_server_exceptions=True)

    payload = {"update_type": "MESSAGE_CREATED", "payload": {"x": 1}}
    resp = client.post("/", json=payload)

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert handled.get("obj") is event


async def test_handle_webhook_default_path_serves_at_root(monkeypatch):
    """При path по умолчанию (DEFAULT_PATH) ручка доступна по POST /."""
    dp = Dispatcher()

    async def fake_startup(bot):
        pass

    dp.startup = fake_startup

    async def fake_process_update_webhook(event_json, bot):
        return None

    monkeypatch.setattr(
        integration_module,
        "process_update_webhook",
        fake_process_update_webhook,
    )

    async def fake_handle_noop(event_object):
        pass

    dp.handle = fake_handle_noop

    webhook = FastAPIMaxWebhook(dp=dp, bot=DummyBot())
    app = webhook.create_app(path=DEFAULT_PATH)
    client = TestClient(app, raise_server_exceptions=True)

    resp = client.post("/", json={"update_type": "unknown"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


async def test_handle_webhook_custom_path_serves_at_that_path(monkeypatch):
    """При кастомном path ручка доступна по этому пути;
    POST / возвращает 404.
    """
    dp = Dispatcher()

    async def fake_startup(bot):
        pass

    dp.startup = fake_startup

    event = DummyEvent(update_type="MESSAGE_CREATED")

    async def fake_process_update_webhook(event_json, bot):
        return event

    monkeypatch.setattr(
        integration_module,
        "process_update_webhook",
        fake_process_update_webhook,
    )

    handled = {}

    async def fake_handle(event_object):
        handled["obj"] = event_object

    dp.handle = fake_handle

    webhook_path = "/webhook/custom"
    wh = FastAPIMaxWebhook(dp=dp, bot=DummyBot())
    app = wh.create_app(path=webhook_path)
    client = TestClient(app, raise_server_exceptions=True)

    payload = {"update_type": "MESSAGE_CREATED", "payload": {}}

    resp_custom = client.post(webhook_path, json=payload)
    assert resp_custom.status_code == 200
    assert resp_custom.json() == {"ok": True}
    assert handled.get("obj") is event

    resp_root = client.post("/", json=payload)
    assert resp_root.status_code == 404
