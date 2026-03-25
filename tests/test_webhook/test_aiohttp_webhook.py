"""Тесты AiohttpMaxWebhook."""

import asyncio
from http import HTTPStatus

import maxapi.webhook.base as integration_module
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from maxapi import Dispatcher
from maxapi.webhook.aiohttp import AiohttpMaxWebhook


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
# on_startup
# ---------------------------------------------------------------------------


async def test_on_startup_calls_dp_startup():
    """on_startup() вызывает dp.startup(bot) при старте приложения."""
    dp = Dispatcher()
    called_with = {}

    async def fake_startup(bot):
        called_with["bot"] = bot

    dp.startup = fake_startup

    bot = DummyBot()
    wh = AiohttpMaxWebhook(dp=dp, bot=bot)
    await wh.on_startup(web.Application())

    assert called_with.get("bot") is bot


# ---------------------------------------------------------------------------
# setup / route
# ---------------------------------------------------------------------------


async def test_webhook_setup_registers_route_and_handles_request(monkeypatch):
    """setup() регистрирует маршрут в переданном aiohttp-приложении."""
    dp = Dispatcher()
    _patch_startup(dp)

    handled = {}

    async def fake_process(event_json, bot):
        handled["json"] = event_json
        return None

    monkeypatch.setattr(
        integration_module, "process_update_webhook", fake_process
    )

    app = web.Application()
    wh = AiohttpMaxWebhook(dp=dp, bot=DummyBot())
    wh.setup(app, path="/test-webhook")

    async with TestClient(TestServer(app)) as client:
        payload = {"hello": "world"}
        resp = await client.post("/test-webhook", json=payload)

        assert resp.status == HTTPStatus.OK
        assert await resp.json() == {"ok": True}
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

    wh = AiohttpMaxWebhook(dp=dp, bot=DummyBot())

    async with TestClient(TestServer(wh.create_app(path="/"))) as client:
        resp = await client.post("/", json={"update_type": "MESSAGE_CREATED"})
        assert resp.status == HTTPStatus.OK

    assert len(tasks_created) == 1


# ---------------------------------------------------------------------------
# create_app
# ---------------------------------------------------------------------------


async def test_create_app_returns_app_with_route(monkeypatch):
    """create_app() создаёт aiohttp-приложение
    с зарегистрированным маршрутом.
    """
    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process(monkeypatch)

    wh = AiohttpMaxWebhook(dp=dp, bot=DummyBot())
    app = wh.create_app(path="/webhook")

    async with TestClient(TestServer(app)) as client:
        resp = await client.post("/webhook", json={"update_type": "unknown"})
        assert resp.status == HTTPStatus.OK
        assert await resp.json() == {"ok": True}

        resp_wrong = await client.post("/other", json={})
        assert resp_wrong.status == 404


async def test_create_app_calls_on_startup(monkeypatch):
    """create_app() регистрирует on_startup —
    dp.startup вызывается при старте.
    """
    dp = Dispatcher()
    _patch_process(monkeypatch)

    startup_called = False

    async def fake_startup(bot):
        nonlocal startup_called
        startup_called = True

    dp.startup = fake_startup

    wh = AiohttpMaxWebhook(dp=dp, bot=DummyBot())

    async with TestClient(TestServer(wh.create_app(path="/"))) as client:
        await client.post("/", json={"update_type": "unknown"})

    assert startup_called


# ---------------------------------------------------------------------------
# secret
# ---------------------------------------------------------------------------


async def test_secret_rejects_request_without_header(monkeypatch):
    """Запрос без X-Max-Bot-Api-Secret возвращает 403."""
    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process(monkeypatch)

    wh = AiohttpMaxWebhook(dp=dp, bot=DummyBot(), secret="my-secret")

    async with TestClient(TestServer(wh.create_app(path="/"))) as client:
        resp = await client.post("/", json={"update_type": "unknown"})
        assert resp.status == HTTPStatus.FORBIDDEN


async def test_secret_rejects_request_with_wrong_header(monkeypatch):
    """Запрос с неверным X-Max-Bot-Api-Secret возвращает 403."""
    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process(monkeypatch)

    wh = AiohttpMaxWebhook(dp=dp, bot=DummyBot(), secret="my-secret")

    async with TestClient(TestServer(wh.create_app(path="/"))) as client:
        resp = await client.post(
            "/",
            json={"update_type": "unknown"},
            headers={"X-Max-Bot-Api-Secret": "wrong-secret"},
        )
        assert resp.status == HTTPStatus.FORBIDDEN


async def test_secret_accepts_request_with_correct_header(monkeypatch):
    """Запрос с правильным X-Max-Bot-Api-Secret проходит и возвращает 200."""
    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process(monkeypatch)

    wh = AiohttpMaxWebhook(dp=dp, bot=DummyBot(), secret="my-secret")

    async with TestClient(TestServer(wh.create_app(path="/"))) as client:
        resp = await client.post(
            "/",
            json={"update_type": "unknown"},
            headers={"X-Max-Bot-Api-Secret": "my-secret"},
        )
        assert resp.status == HTTPStatus.OK


async def test_no_secret_accepts_any_request(monkeypatch):
    """Если secret не задан, запросы принимаются без проверки заголовка."""
    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process(monkeypatch)

    wh = AiohttpMaxWebhook(dp=dp, bot=DummyBot())

    async with TestClient(TestServer(wh.create_app(path="/"))) as client:
        resp = await client.post("/", json={"update_type": "unknown"})
        assert resp.status == HTTPStatus.OK


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


async def test_run_sets_up_runner_and_starts_site(monkeypatch):
    """run() вызывает setup(), start() и wait(),
    а при завершении — cleanup().
    """
    from aiohttp import web

    calls = []

    class FakeRunner:
        def __init__(self, app, **kwargs):
            pass

        async def setup(self):
            calls.append("setup")

        async def cleanup(self):
            calls.append("cleanup")

    class FakeSite:
        def __init__(self, runner, host, port):
            self.host = host
            self.port = port

        async def start(self):
            calls.append(f"start:{self.host}:{self.port}")

    class FakeEvent:
        async def wait(self):
            calls.append("wait")

    monkeypatch.setattr(web, "AppRunner", FakeRunner)
    monkeypatch.setattr(web, "TCPSite", FakeSite)
    monkeypatch.setattr(asyncio, "Event", FakeEvent)

    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process(monkeypatch)

    wh = AiohttpMaxWebhook(dp=dp, bot=DummyBot())
    await wh.run(host="127.0.0.1", port=9999, path="/wh")

    assert calls == ["setup", "start:127.0.0.1:9999", "wait", "cleanup"]


async def test_run_cleans_up_on_cancellation(monkeypatch):
    """run() вызывает runner.cleanup() даже при CancelledError."""
    from aiohttp import web

    cleanup_called = False

    class FakeRunner:
        def __init__(self, app, **kwargs):
            pass

        async def setup(self):
            pass

        async def cleanup(self):
            nonlocal cleanup_called
            cleanup_called = True

    class FakeSite:
        def __init__(self, runner, host, port):
            pass

        async def start(self):
            pass

    class FakeEvent:
        async def wait(self):
            raise asyncio.CancelledError

    monkeypatch.setattr(web, "AppRunner", FakeRunner)
    monkeypatch.setattr(web, "TCPSite", FakeSite)
    monkeypatch.setattr(asyncio, "Event", FakeEvent)

    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process(monkeypatch)

    wh = AiohttpMaxWebhook(dp=dp, bot=DummyBot())
    with pytest.raises(asyncio.CancelledError):
        await wh.run(host="127.0.0.1", port=9999)

    assert cleanup_called


async def test_run_passes_kwargs_to_app_runner(monkeypatch):
    """run() передаёт **kwargs в AppRunner."""
    from aiohttp import web

    received_kwargs = {}

    class FakeRunner:
        def __init__(self, app, **kwargs):
            received_kwargs.update(kwargs)

        async def setup(self):
            pass

        async def cleanup(self):
            pass

    class FakeSite:
        def __init__(self, runner, host, port):
            pass

        async def start(self):
            pass

    class FakeEvent:
        async def wait(self):
            pass

    monkeypatch.setattr(web, "AppRunner", FakeRunner)
    monkeypatch.setattr(web, "TCPSite", FakeSite)
    monkeypatch.setattr(asyncio, "Event", FakeEvent)

    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process(monkeypatch)

    wh = AiohttpMaxWebhook(dp=dp, bot=DummyBot())
    await wh.run(host="127.0.0.1", port=9999, access_log=False)

    assert received_kwargs.get("access_log") is False
