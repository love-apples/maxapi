"""Тесты Dispatcher.startup."""

from maxapi import Dispatcher


class DummyBot:
    pass


# ---------------------------------------------------------------------------
# Dispatcher.startup
# ---------------------------------------------------------------------------


async def test_dispatcher_startup_calls_ready(monkeypatch):
    """startup() делегирует вызов в приватный __ready."""
    dp = Dispatcher()
    called_with = {}

    async def fake_ready(bot):
        called_with["bot"] = bot

    monkeypatch.setattr(dp, "_Dispatcher__ready", fake_ready)

    bot = DummyBot()
    await dp.startup(bot)

    assert called_with.get("bot") is bot
