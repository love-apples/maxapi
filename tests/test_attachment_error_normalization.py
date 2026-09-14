"""Тесты нормализации ошибок success=False с HTTP 200.

Покрывает обработку в connection/base.py: MAX API иногда отвечает
HTTP 200 с success=False и текстовым message вместо machine-readable
code (например, для attachment.file.not.processed). Нормализация
кода происходит в одном месте (``_normalize_error_code``) и не
превращается в общее правило "raise на любой success=False" —
часть ответов (например AddedMembersChat) легитимно возвращает
success=False вместе с деталями вроде failed_user_details.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from maxapi import Bot
from maxapi.connection.base import (
    RETRYABLE_ATTACHMENT_ERROR_CODES,
    BaseConnection,
    _normalize_error_code,
)
from maxapi.enums.http_method import HTTPMethod
from maxapi.exceptions.max import MaxApiError
from maxapi.methods.edit_message import EditMessage
from maxapi.methods.send_message import SendMessage
from maxapi.methods.types.added_members_chat import AddedMembersChat


def _make_response(status, *, ok=None, json_data=None, text=None):
    """Создаёт мок aiohttp-ответа с async-методами.

    request() читает тело через .text() и парсит его вручную
    (см. _parse_json_object в connection/base.py), поэтому мок
    должен отдавать текстовое тело, а не только .json().
    """
    resp = MagicMock()
    resp.status = status
    resp.ok = ok if ok is not None else (200 <= status < 300)
    resp.read = AsyncMock()
    if text is None:
        text = "" if json_data is None else json.dumps(json_data)
    resp.text = AsyncMock(return_value=text)
    if json_data is not None:
        resp.json = AsyncMock(return_value=json_data)
    return resp


class TestNormalizeErrorCode:
    """Юнит-тесты чистой функции нормализации."""

    def test_known_message_substring_returns_code(self):
        raw = {
            "success": False,
            "message": "error: attachment.file.not.processed happened",
        }
        assert (
            _normalize_error_code(raw) == "attachment.file.not.processed"
        )

    def test_existing_code_is_not_overwritten(self):
        """Если code уже есть в ответе — нормализация его не трогает."""
        raw = {
            "success": False,
            "code": "some.other.code",
            "message": "attachment.file.not.processed",
        }
        assert _normalize_error_code(raw) is None

    def test_unknown_message_returns_none(self):
        """Неизвестный текст ошибки не нормализуется — не считается
        ошибкой библиотеки (например, AddedMembersChat)."""
        raw = {
            "success": False,
            "message": "some users could not be added",
        }
        assert _normalize_error_code(raw) is None

    def test_no_message_returns_none(self):
        raw = {"success": False}
        assert _normalize_error_code(raw) is None


class TestRequestSuccessFalseHandling:
    """Тесты обработки success=False в BaseConnection.request()."""

    @pytest.fixture
    def bot(self, mock_bot_token):
        bot = Bot(token=mock_bot_token)
        session = MagicMock()
        session.closed = False
        bot.session = session
        return bot

    @pytest.mark.asyncio
    async def test_known_attachment_error_raises_with_normalized_code(
        self, bot
    ):
        """success=False + известная подстрока message -> MaxApiError
        с нормализованным raw["code"], несмотря на HTTP 200."""
        response = _make_response(
            200,
            json_data={
                "success": False,
                "message": "attachment.file.not.processed: retry later",
            },
        )
        bot.session.request = AsyncMock(return_value=response)

        base = BaseConnection()
        base.bot = bot

        with pytest.raises(MaxApiError) as exc_info:
            await base.request(
                method=HTTPMethod.PUT,
                path="/messages",
                is_return_raw=True,
            )

        assert exc_info.value.code == 400
        assert (
            exc_info.value.raw["code"] == "attachment.file.not.processed"
        )

    @pytest.mark.asyncio
    async def test_unrelated_success_false_does_not_raise(self, bot):
        """success=False без известного паттерна (например ответ
        AddedMembersChat с failed_user_details) должен пройти
        нормально, без исключения."""
        response = _make_response(
            200,
            json_data={
                "success": False,
                "message": "some members were not added",
                "failed_user_ids": [1, 2, 3],
            },
        )
        bot.session.request = AsyncMock(return_value=response)

        base = BaseConnection()
        base.bot = bot

        result = await base.request(
            method=HTTPMethod.POST,
            path="/chats/1/members",
            is_return_raw=True,
        )

        assert result["success"] is False
        assert "code" not in result

    @pytest.mark.asyncio
    async def test_added_members_chat_with_failed_details_not_raised(
        self, bot
    ):
        """AddedMembersChat легитимно возвращает
        success=False с failed_user_details и НЕ должен
        интерпретироваться как ошибка библиотеки."""
        response = _make_response(
            200,
            json_data={
                "success": False,
                "failed_user_details": [
                    {
                        "error_code": "add.participant.privacy",
                        "user_ids": [42],
                    }
                ],
            },
        )
        bot.session.request = AsyncMock(return_value=response)

        base = BaseConnection()
        base.bot = bot

        result = await base.request(
            method=HTTPMethod.POST,
            path="/chats/1/members",
            model=AddedMembersChat,
        )

        assert isinstance(result, AddedMembersChat)
        assert result.success is False
        assert result.failed_user_details[0].user_ids == [42]

    @pytest.mark.asyncio
    async def test_success_true_not_affected(self, bot):
        """success=True не проходит через нормализацию ошибок."""
        response = _make_response(200, json_data={"success": True})
        bot.session.request = AsyncMock(return_value=response)

        base = BaseConnection()
        base.bot = bot

        result = await base.request(
            method=HTTPMethod.GET,
            path="/test",
            is_return_raw=True,
        )

        assert result == {"success": True}


class TestRetryableAttachmentErrorCodesShared:
    """RETRYABLE_ATTACHMENT_ERROR_CODES должен использоваться
    одинаково в SendMessage и EditMessage — раньше нормализация
    'attachment.file.not.processed' была добавлена только в
    EditMessage.fetch(), из-за чего SendMessage её не ретраил."""

    def test_contains_both_known_codes(self):
        assert {
            "attachment.not.ready",
            "attachment.file.not.processed",
        } == RETRYABLE_ATTACHMENT_ERROR_CODES

    @pytest.mark.asyncio
    async def test_send_message_retries_on_normalized_code(
        self, mock_bot_token
    ):
        bot = Bot(
            token=mock_bot_token,
            after_upload_attempts=3,
            after_upload_retry_delay=0.01,
        )
        bot.session = AsyncMock()

        send = SendMessage(bot=bot, chat_id=123, text="test")

        error = MaxApiError(
            code=400, raw={"code": "attachment.file.not.processed"}
        )
        success_response = MagicMock()
        success_response.message = MagicMock()

        with (
            patch.object(
                BaseConnection,
                "request",
                new_callable=AsyncMock,
                side_effect=[error, success_response],
            ) as mock_request,
            patch("maxapi.methods.send_message.asyncio.sleep"),
        ):
            result = await send.fetch()

        assert result == success_response
        assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_edit_message_retries_on_normalized_code(
        self, mock_bot_token
    ):
        bot = Bot(
            token=mock_bot_token,
            after_upload_attempts=3,
            after_upload_retry_delay=0.01,
        )
        bot.session = AsyncMock()

        edit = EditMessage(bot=bot, message_id="mid.123", text="updated")

        error = MaxApiError(
            code=400, raw={"code": "attachment.file.not.processed"}
        )
        success_response = MagicMock()
        success_response.message = MagicMock()

        with (
            patch.object(
                BaseConnection,
                "request",
                new_callable=AsyncMock,
                side_effect=[error, success_response],
            ) as mock_request,
            patch("maxapi.methods.edit_message.asyncio.sleep"),
        ):
            result = await edit.fetch()

        assert result == success_response
        assert mock_request.call_count == 2
