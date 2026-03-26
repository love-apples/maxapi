"""Тесты поведения вебхука при падении обработчика.

Если dp.handle бросает необработанное исключение — вебхук должен
вернуть 500, чтобы MAX знал о сбое доставки.
"""

from http import HTTPStatus

import maxapi.webhook.base as base_module
import pytest
from maxapi import Dispatcher


class DummyBot:
    pass


class DummyEvent:
    update_type = "MESSAGE_CREATED"

    def get_ids(self):
        return (123, 456)


def _patch_startup(dp):
    async def fake_startup(bot):
        pass

    dp.startup = fake_startup


def _patch_process_with_event(monkeypatch):
    """Патчим process_update_webhook так, чтобы вернулся DummyEvent."""
    event = DummyEvent()

    async def fake_process(event_json, bot):
        return event

    monkeypatch.setattr(base_module, "process_update_webhook", fake_process)
    return event


def _make_failing_handle():
    async def failing_handle(event_object):
        raise RuntimeError("обработчик упал")

    return failing_handle


# ---------------------------------------------------------------------------
# aiohttp
# ---------------------------------------------------------------------------


async def test_aiohttp_returns_500_when_handler_raises(monkeypatch):
    """AiohttpMaxWebhook возвращает 500, если dp.handle падает."""
    from aiohttp.test_utils import TestClient, TestServer
    from maxapi.webhook.aiohttp import AiohttpMaxWebhook

    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process_with_event(monkeypatch)
    dp.handle = _make_failing_handle()

    wh = AiohttpMaxWebhook(dp=dp, bot=DummyBot())
    async with TestClient(TestServer(wh.create_app(path="/"))) as client:
        resp = await client.post("/", json={"update_type": "MESSAGE_CREATED"})
        assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR


# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------


def test_fastapi_returns_500_when_handler_raises(monkeypatch):
    """FastAPIMaxWebhook возвращает 500, если dp.handle падает."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from maxapi.webhook.fastapi import FastAPIMaxWebhook

    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process_with_event(monkeypatch)
    dp.handle = _make_failing_handle()

    wh = FastAPIMaxWebhook(dp=dp, bot=DummyBot())
    client = TestClient(wh.create_app(path="/"), raise_server_exceptions=False)
    resp = client.post("/", json={"update_type": "MESSAGE_CREATED"})
    assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


# ---------------------------------------------------------------------------
# Litestar
# ---------------------------------------------------------------------------


def test_litestar_returns_500_when_handler_raises(monkeypatch):
    """LitestarMaxWebhook возвращает 500, если dp.handle падает."""
    from litestar.testing import TestClient
    from maxapi.webhook.litestar import LitestarMaxWebhook

    dp = Dispatcher()
    _patch_startup(dp)
    _patch_process_with_event(monkeypatch)
    dp.handle = _make_failing_handle()

    wh = LitestarMaxWebhook(dp=dp, bot=DummyBot())
    with TestClient(
        wh.create_app(path="/"), raise_server_exceptions=False
    ) as client:
        resp = client.post("/", json={"update_type": "MESSAGE_CREATED"})
        assert resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
