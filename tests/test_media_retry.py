"""Тесты configurable retry для attachment.not.ready (media upload)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from maxapi import Bot
from maxapi.connection.base import BaseConnection
from maxapi.exceptions.max import MaxApiError
from maxapi.methods.edit_message import EditMessage
from maxapi.methods.send_message import SendMessage


def _make_attachment_not_ready_error():
    """Создаёт MaxApiError с кодом attachment.not.ready."""
    return MaxApiError(
        code=400,
        raw={"code": "attachment.not.ready"},
    )


def _make_other_api_error():
    """Создаёт MaxApiError с другим кодом."""
    return MaxApiError(
        code=400,
        raw={"code": "some.other.error"},
    )


class TestBotMediaRetryConfig:
    """Тесты конфигурации media retry в Bot."""

    def test_default_values(self, mock_bot_token):
        """По умолчанию: 5 попыток, 2.0с задержка."""
        bot = Bot(token=mock_bot_token)
        assert bot.after_upload_attempts == 5
        assert bot.after_upload_retry_delay == 2.0

    def test_custom_attempts(self, mock_bot_token):
        """Пользовательское количество попыток."""
        bot = Bot(
            token=mock_bot_token,
            after_upload_attempts=10,
        )
        assert bot.after_upload_attempts == 10
        assert bot.after_upload_retry_delay == 2.0

    def test_custom_delay(self, mock_bot_token):
        """Пользовательская задержка."""
        bot = Bot(
            token=mock_bot_token,
            after_upload_retry_delay=5.0,
        )
        assert bot.after_upload_attempts == 5
        assert bot.after_upload_retry_delay == 5.0

    def test_custom_both(self, mock_bot_token):
        """Пользовательские оба параметра."""
        bot = Bot(
            token=mock_bot_token,
            after_upload_attempts=15,
            after_upload_retry_delay=3.0,
        )
        assert bot.after_upload_attempts == 15
        assert bot.after_upload_retry_delay == 3.0

    def test_zero_attempts_raises(self, mock_bot_token):
        """Ноль попыток вызывает ValueError."""
        with pytest.raises(
            ValueError, match="after_upload_attempts"
        ):
            Bot(
                token=mock_bot_token,
                after_upload_attempts=0,
            )

    def test_negative_attempts_raises(self, mock_bot_token):
        """Отрицательное количество попыток — ValueError."""
        with pytest.raises(
            ValueError, match="after_upload_attempts"
        ):
            Bot(
                token=mock_bot_token,
                after_upload_attempts=-1,
            )

    def test_negative_delay_raises(self, mock_bot_token):
        """Отрицательная задержка — ValueError."""
        with pytest.raises(
            ValueError, match="after_upload_retry_delay"
        ):
            Bot(
                token=mock_bot_token,
                after_upload_retry_delay=-1.0,
            )

    def test_zero_delay(self, mock_bot_token):
        """Нулевая задержка — валидное значение."""
        bot = Bot(
            token=mock_bot_token,
            after_upload_retry_delay=0.0,
        )
        assert bot.after_upload_retry_delay == 0.0


class TestSendMessageMediaRetry:
    """Тесты retry attachment.not.ready в send_message."""

    @pytest.fixture
    def bot_custom_retry(self, mock_bot_token):
        """Бот с увеличенным retry для медиа."""
        bot = Bot(
            token=mock_bot_token,
            after_upload_attempts=3,
            after_upload_retry_delay=0.01,
        )
        session = AsyncMock()
        bot.session = session
        return bot

    @pytest.mark.asyncio
    async def test_retry_on_attachment_not_ready(
        self, bot_custom_retry
    ):
        """Retry при attachment.not.ready и успех."""
        send = SendMessage(
            bot=bot_custom_retry,
            chat_id=123,
            text="test",
        )

        success_response = MagicMock()
        success_response.message = MagicMock()

        with patch.object(
            BaseConnection,
            "request",
            new_callable=AsyncMock,
            side_effect=[
                _make_attachment_not_ready_error(),
                success_response,
            ],
        ) as mock_request, patch(
            "maxapi.methods.send_message.asyncio.sleep"
        ) as mock_sleep:
            result = await send.fetch()

        assert result == success_response
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once_with(0.01)

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises_runtime_error(
        self, bot_custom_retry
    ):
        """Исчерпание попыток бросает RuntimeError."""
        send = SendMessage(
            bot=bot_custom_retry,
            chat_id=123,
            text="test",
        )

        with patch.object(
            BaseConnection,
            "request",
            new_callable=AsyncMock,
            side_effect=_make_attachment_not_ready_error(),
        ) as mock_request, patch(
            "maxapi.methods.send_message.asyncio.sleep"
        ), pytest.raises(
            RuntimeError, match="отправить"
        ):
            await send.fetch()

        assert mock_request.call_count == 3

    @pytest.mark.asyncio
    async def test_other_api_error_not_retried(
        self, bot_custom_retry
    ):
        """Другие MaxApiError не ретраятся."""
        send = SendMessage(
            bot=bot_custom_retry,
            chat_id=123,
            text="test",
        )

        with patch.object(
            BaseConnection,
            "request",
            new_callable=AsyncMock,
            side_effect=_make_other_api_error(),
        ) as mock_request, pytest.raises(MaxApiError):
            await send.fetch()

        assert mock_request.call_count == 1

    @pytest.mark.asyncio
    async def test_uses_bot_retry_delay(self, mock_bot_token):
        """Использует задержку из bot.after_upload_retry_delay."""
        bot = Bot(
            token=mock_bot_token,
            after_upload_attempts=2,
            after_upload_retry_delay=7.5,
        )
        bot.session = AsyncMock()

        send = SendMessage(bot=bot, chat_id=123, text="test")

        success_response = MagicMock()
        success_response.message = MagicMock()

        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with patch.object(
            BaseConnection,
            "request",
            new_callable=AsyncMock,
            side_effect=[
                _make_attachment_not_ready_error(),
                success_response,
            ],
        ), patch(
            "maxapi.methods.send_message.asyncio.sleep",
            side_effect=mock_sleep,
        ):
            await send.fetch()

        assert sleep_calls == [7.5]

    @pytest.mark.asyncio
    async def test_default_bot_uses_5_attempts(
        self, mock_bot_token
    ):
        """Бот с дефолтами использует 5 попыток."""
        bot = Bot(token=mock_bot_token)
        bot.session = AsyncMock()

        send = SendMessage(bot=bot, chat_id=123, text="test")

        with patch.object(
            BaseConnection,
            "request",
            new_callable=AsyncMock,
            side_effect=_make_attachment_not_ready_error(),
        ) as mock_request, patch(
            "maxapi.methods.send_message.asyncio.sleep"
        ), pytest.raises(RuntimeError):
            await send.fetch()

        assert mock_request.call_count == 5


class TestEditMessageMediaRetry:
    """Тесты retry attachment.not.ready в edit_message."""

    @pytest.fixture
    def bot_custom_retry(self, mock_bot_token):
        """Бот с увеличенным retry для медиа."""
        bot = Bot(
            token=mock_bot_token,
            after_upload_attempts=3,
            after_upload_retry_delay=0.01,
        )
        session = AsyncMock()
        bot.session = session
        return bot

    @pytest.mark.asyncio
    async def test_retry_on_attachment_not_ready(
        self, bot_custom_retry
    ):
        """Retry при attachment.not.ready и успех."""
        edit = EditMessage(
            bot=bot_custom_retry,
            message_id="mid.123",
            text="updated",
        )

        success_response = MagicMock()
        success_response.message = MagicMock()

        with patch.object(
            BaseConnection,
            "request",
            new_callable=AsyncMock,
            side_effect=[
                _make_attachment_not_ready_error(),
                success_response,
            ],
        ) as mock_request, patch(
            "maxapi.methods.edit_message.asyncio.sleep"
        ) as mock_sleep:
            result = await edit.fetch()

        assert result == success_response
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once_with(0.01)

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises_runtime_error(
        self, bot_custom_retry
    ):
        """Исчерпание попыток бросает RuntimeError."""
        edit = EditMessage(
            bot=bot_custom_retry,
            message_id="mid.123",
            text="updated",
        )

        with patch.object(
            BaseConnection,
            "request",
            new_callable=AsyncMock,
            side_effect=_make_attachment_not_ready_error(),
        ) as mock_request, patch(
            "maxapi.methods.edit_message.asyncio.sleep"
        ), pytest.raises(
            RuntimeError, match="отредактировать"
        ):
            await edit.fetch()

        assert mock_request.call_count == 3

    @pytest.mark.asyncio
    async def test_other_api_error_not_retried(
        self, bot_custom_retry
    ):
        """Другие MaxApiError не ретраятся."""
        edit = EditMessage(
            bot=bot_custom_retry,
            message_id="mid.123",
            text="updated",
        )

        with patch.object(
            BaseConnection,
            "request",
            new_callable=AsyncMock,
            side_effect=_make_other_api_error(),
        ) as mock_request, pytest.raises(MaxApiError):
            await edit.fetch()

        assert mock_request.call_count == 1

    @pytest.mark.asyncio
    async def test_uses_bot_retry_delay(self, mock_bot_token):
        """Использует задержку из bot.after_upload_retry_delay."""
        bot = Bot(
            token=mock_bot_token,
            after_upload_attempts=2,
            after_upload_retry_delay=5.0,
        )
        bot.session = AsyncMock()

        edit = EditMessage(
            bot=bot, message_id="mid.123", text="updated"
        )

        success_response = MagicMock()
        success_response.message = MagicMock()

        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with patch.object(
            BaseConnection,
            "request",
            new_callable=AsyncMock,
            side_effect=[
                _make_attachment_not_ready_error(),
                success_response,
            ],
        ), patch(
            "maxapi.methods.edit_message.asyncio.sleep",
            side_effect=mock_sleep,
        ):
            await edit.fetch()

        assert sleep_calls == [5.0]


class TestBackwardCompatibility:
    """Тесты обратной совместимости."""

    def test_base_connection_constants_still_exist(self):
        """Константы в BaseConnection сохранены."""
        assert BaseConnection.RETRY_DELAY == 2
        assert BaseConnection.ATTEMPTS_COUNT == 5

    def test_bot_without_new_params(self, mock_bot_token):
        """Бот без новых параметров работает как раньше."""
        bot = Bot(token=mock_bot_token)
        assert bot.after_upload_attempts == 5
        assert bot.after_upload_retry_delay == 2.0
