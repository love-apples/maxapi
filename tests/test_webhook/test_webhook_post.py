import asyncio
import sys

import maxapi.webhook.base as integration_module
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from maxapi import Dispatcher
from maxapi.webhook.fastapi import FastAPIMaxWebhook

pytest.importorskip("fastapi")


class DummyBot:
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_startup(dp):
    async def fake_startup(bot):
        pass

    dp.startup = fake_startup


def _patch_process(monkeypatch, return_value=None):
    async def fake_process(event_json, bot):
        return return_value

    monkeypatch.setattr(
        integration_module, "process_update_webhook", fake_process
    )


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_raises_import_error_without_fastapi(monkeypatch):
    """FastAPIMaxWebhook.__init__ поднимает ImportError,
    если fastapi не установлен.
    """
    monkeypatch.setitem(sys.modules, "fastapi", None)
    with pytest.raises(ImportError, match="fastapi is not installed"):
        FastAPIMaxWebhook(dp=Dispatcher(), bot=DummyBot())


# ---------------------------------------------------------------------------
# lifespan
# ---------------------------------------------------------------------------


async def test_lifespan_calls_dp_startup():
    """lifespan() вызывает dp.startup(bot) при входе в контекст."""
    dp = Dispatcher()
    called_with = {}

    async def fake_startup(bot):
        called_with["bot"] = bot

    dp.startup = fake_startup

    bot = DummyBot()
    wh = FastAPIMaxWebhook(dp=dp, bot=bot)

    async with wh.lifespan(FastAPI()):
        pass

    assert called_with.get("bot") is bot


# ---------------------------------------------------------------------------
# setup / route
# ---------------------------------------------------------------------------


def test_webhook_setup_registers_route_and_handles_request(monkeypatch):
    """setup() регистрирует маршрут в переданном FastAPI-приложении."""
    dp = Dispatcher()
    _patch_startup(dp)

    handled = {}

    async def fake_process(event_json, bot):
        handled["json"] = event_json
        return None

    monkeypatch.setattr(
        integration_module, "process_update_webhook", fake_process
    )

    app = FastAPI()
    wh = FastAPIMaxWebhook(dp=dp, bot=DummyBot())
    wh.setup(app, path="/test-webhook")

    payload = {"hello": "world"}
    resp = TestClient(app).post("/test-webhook", json=payload)

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert handled["json"] == payload


async def test_use_create_task_schedules_handle_as_task(monkeypatch):
    """Когда use_create_task=True, handle планируется через
    create_task, а не await.
    """
    dp = Dispatcher()
    dp.use_create_task = True
    _patch_startup(dp)

    event = object()
    _patch_process(monkeypatch, return_value=event)

    tasks_created = []

    async def fake_handle(ev):
        pass

    dp.handle = fake_handle

    original_create_task = asyncio.create_task

    def spy_create_task(coro, **kwargs):
        tasks_created.append(True)
        return original_create_task(coro, **kwargs)

    monkeypatch.setattr(asyncio, "create_task", spy_create_task)

    wh = FastAPIMaxWebhook(dp=dp, bot=DummyBot())
    app = wh.create_app(path="/")

    resp = TestClient(app).post("/", json={"update_type": "MESSAGE_CREATED"})

    assert resp.status_code == 200
    assert len(tasks_created) == 1


# ---------------------------------------------------------------------------
# create_app
# ---------------------------------------------------------------------------


def test_create_app_returns_app_with_route(monkeypatch):
    """create_app() создаёт FastAPI-приложение
    с зарегистрированным маршрутом.
    """
    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process(monkeypatch)

    wh = FastAPIMaxWebhook(dp=dp, bot=DummyBot())
    client = TestClient(wh.create_app(path="/webhook"))

    assert (
        client.post("/webhook", json={"update_type": "unknown"}).status_code
        == 200
    )
    assert client.post("/other", json={}).status_code == 404


# ---------------------------------------------------------------------------
# secret
# ---------------------------------------------------------------------------


def test_secret_rejects_request_without_header(monkeypatch):
    """Запрос без X-Max-Bot-Api-Secret возвращает 403."""
    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process(monkeypatch)

    wh = FastAPIMaxWebhook(dp=dp, bot=DummyBot(), secret="my-secret")
    client = TestClient(wh.create_app(path="/"))

    assert client.post("/", json={"update_type": "unknown"}).status_code == 403


def test_secret_rejects_request_with_wrong_header(monkeypatch):
    """Запрос с неверным X-Max-Bot-Api-Secret возвращает 403."""
    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process(monkeypatch)

    wh = FastAPIMaxWebhook(dp=dp, bot=DummyBot(), secret="my-secret")
    client = TestClient(wh.create_app(path="/"))

    resp = client.post(
        "/",
        json={"update_type": "unknown"},
        headers={"X-Max-Bot-Api-Secret": "wrong-secret"},
    )
    assert resp.status_code == 403


def test_secret_accepts_request_with_correct_header(monkeypatch):
    """Запрос с правильным X-Max-Bot-Api-Secret проходит и возвращает 200."""
    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process(monkeypatch)

    wh = FastAPIMaxWebhook(dp=dp, bot=DummyBot(), secret="my-secret")
    client = TestClient(wh.create_app(path="/"))

    resp = client.post(
        "/",
        json={"update_type": "unknown"},
        headers={"X-Max-Bot-Api-Secret": "my-secret"},
    )
    assert resp.status_code == 200


def test_no_secret_accepts_any_request(monkeypatch):
    """Если secret не задан, запросы принимаются без проверки заголовка."""
    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process(monkeypatch)

    wh = FastAPIMaxWebhook(dp=dp, bot=DummyBot())
    client = TestClient(wh.create_app(path="/"))

    assert client.post("/", json={"update_type": "unknown"}).status_code == 200


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


async def test_run_calls_uvicorn_serve(monkeypatch):
    """run() создаёт uvicorn.Config + Server и вызывает serve()."""
    import uvicorn

    serve_called = False

    class FakeConfig:
        def __init__(self, *, app, host, port, **kwargs):
            pass

    class FakeServer:
        def __init__(self, config):
            pass

        async def serve(self):
            nonlocal serve_called
            serve_called = True

    monkeypatch.setattr(uvicorn, "Config", FakeConfig)
    monkeypatch.setattr(uvicorn, "Server", FakeServer)

    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process(monkeypatch)

    wh = FastAPIMaxWebhook(dp=dp, bot=DummyBot())
    await wh.run(host="127.0.0.1", port=9999)

    assert serve_called


async def test_run_passes_host_port_to_config(monkeypatch):
    """run() передаёт host и port в uvicorn.Config."""
    import uvicorn

    captured = {}

    class FakeConfig:
        def __init__(self, *, app, host, port, **kwargs):
            captured["host"] = host
            captured["port"] = port

    class FakeServer:
        def __init__(self, config):
            pass

        async def serve(self):
            pass

    monkeypatch.setattr(uvicorn, "Config", FakeConfig)
    monkeypatch.setattr(uvicorn, "Server", FakeServer)

    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process(monkeypatch)

    wh = FastAPIMaxWebhook(dp=dp, bot=DummyBot())
    await wh.run(host="0.0.0.0", port=8080)

    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 8080


async def test_run_raises_import_error_without_uvicorn(monkeypatch):
    """run() поднимает ImportError, если uvicorn не установлен."""
    monkeypatch.setitem(sys.modules, "uvicorn", None)

    dp = Dispatcher()
    _patch_startup(dp)

    wh = FastAPIMaxWebhook(dp=dp, bot=DummyBot())
    with pytest.raises(ImportError, match="uvicorn is not installed"):
        await wh.run()
