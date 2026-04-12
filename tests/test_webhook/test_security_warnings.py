"""Тесты предупреждений безопасности для webhook-компонентов."""

import logging
import warnings

import pytest
from maxapi import Dispatcher
from maxapi.methods.subscribe_webhook import SubscribeWebhook
from maxapi.webhook.aiohttp import AiohttpMaxWebhook


class DummyBot:
    pass


class TestSubscribeWebhookHttpWarning:
    """Тесты warnings.warn при HTTP URL в SubscribeWebhook."""

    def test_http_url_emits_warning(self, bot):
        """При http:// URL должно быть предупреждение."""
        with pytest.warns(UserWarning, match="не использует HTTPS"):
            SubscribeWebhook(bot=bot, url="http://example.com/webhook")

    def test_https_url_no_warning(self, bot):
        """При https:// URL предупреждений быть не должно."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            SubscribeWebhook(bot=bot, url="https://example.com/webhook")


class TestWebhookSecretNoneWarning:
    """Тесты logger warning при secret=None в BaseMaxWebhook."""

    def test_no_secret_logs_warning(self, caplog):
        """Без secret должен быть warning в логе."""
        dp = Dispatcher()
        with caplog.at_level(logging.WARNING):
            AiohttpMaxWebhook(dp=dp, bot=DummyBot(), secret=None)
        assert any("без secret" in r.message for r in caplog.records)

    def test_with_secret_no_warning(self, caplog):
        """С secret предупреждения быть не должно."""
        dp = Dispatcher()
        with caplog.at_level(logging.WARNING):
            AiohttpMaxWebhook(dp=dp, bot=DummyBot(), secret="my-secret")
        assert not any("без secret" in r.message for r in caplog.records)
