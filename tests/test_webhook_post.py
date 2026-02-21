import pytest

pytest.importorskip("fastapi")

from fastapi import Request
from fastapi.testclient import TestClient
from maxapi.dispatcher import Dispatcher


def test_webhook_post_registers_route_and_handles_request():
    """Проверяет, что декоратор @dp.webhook_post регистрирует маршрут
    в FastAPI-приложении и что обработчик вызывается с JSON-телом.
    """
    dp = Dispatcher()
    received = {}

    @dp.webhook_post("/test-webhook")
    async def handler(request: Request):
        data = await request.json()
        received["data"] = data
        # Возвращаем обычный dict — FastAPI автоматически сериализует
        return {"ok": True, "received": data}

    client = TestClient(dp.webhook_app)

    payload = {"hello": "world"}
    resp = client.post("/test-webhook", json=payload)

    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "received": payload}
    assert received["data"] == payload
