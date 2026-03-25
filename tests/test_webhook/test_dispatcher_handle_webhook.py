"""Тесты Dispatcher.handle_webhook()."""

from maxapi import Dispatcher
from maxapi.webhook.aiohttp import AiohttpMaxWebhook


class DummyBot:
    pass


# ---------------------------------------------------------------------------
# handle_webhook
# ---------------------------------------------------------------------------


async def test_handle_webhook_delegates_to_aiohttp_run(monkeypatch):
    """handle_webhook() создаёт AiohttpMaxWebhook и вызывает run()."""
    run_kwargs = {}

    async def fake_run(self, *, host, port, path, **kwargs):
        run_kwargs.update(host=host, port=port, path=path, **kwargs)

    monkeypatch.setattr(AiohttpMaxWebhook, "run", fake_run)

    dp = Dispatcher()
    await dp.handle_webhook(
        bot=DummyBot(), host="127.0.0.1", port=9000, path="/hook"
    )

    assert run_kwargs["host"] == "127.0.0.1"
    assert run_kwargs["port"] == 9000
    assert run_kwargs["path"] == "/hook"


async def test_handle_webhook_passes_secret_to_webhook(monkeypatch):
    """handle_webhook() передаёт secret в AiohttpMaxWebhook."""
    captured_secret = {}

    original_init = AiohttpMaxWebhook.__init__

    def spy_init(self, dp, bot, *, secret=None):
        captured_secret["secret"] = secret
        original_init(self, dp, bot, secret=secret)

    async def fake_run(self, **kwargs):
        pass

    monkeypatch.setattr(AiohttpMaxWebhook, "__init__", spy_init)
    monkeypatch.setattr(AiohttpMaxWebhook, "run", fake_run)

    dp = Dispatcher()
    await dp.handle_webhook(bot=DummyBot(), secret="s3cr3t")

    assert captured_secret["secret"] == "s3cr3t"


async def test_handle_webhook_default_args(monkeypatch):
    """handle_webhook() использует корректные значения по умолчанию."""
    run_kwargs = {}

    async def fake_run(self, *, host, port, path, **kwargs):
        run_kwargs.update(host=host, port=port, path=path)

    monkeypatch.setattr(AiohttpMaxWebhook, "run", fake_run)

    dp = Dispatcher()
    await dp.handle_webhook(bot=DummyBot())

    assert run_kwargs["host"] == "0.0.0.0"
    assert run_kwargs["port"] == 8080
    assert run_kwargs["path"] == "/"


async def test_handle_webhook_forwards_extra_kwargs(monkeypatch):
    """handle_webhook() передаёт **kwargs в AiohttpMaxWebhook.run()."""
    run_kwargs = {}

    async def fake_run(self, *, host, port, path, **kwargs):
        run_kwargs.update(kwargs)

    monkeypatch.setattr(AiohttpMaxWebhook, "run", fake_run)

    dp = Dispatcher()
    await dp.handle_webhook(bot=DummyBot(), access_log=False)

    assert run_kwargs.get("access_log") is False
