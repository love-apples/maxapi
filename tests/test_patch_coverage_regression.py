from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from maxapi.bot import Bot
from maxapi.connection.base import BaseConnection
from maxapi.enums.attachment import AttachmentType
from maxapi.enums.http_method import HTTPMethod
from maxapi.enums.upload_type import UploadType
from maxapi.exceptions.max import MaxApiError, MaxIconParamsException
from maxapi.methods.edit_chat import EditChat
from maxapi.methods.send_callback import SendCallback
from maxapi.types.attachments.attachment import Attachment
from maxapi.types.attachments.image import PhotoAttachmentRequestPayload
from maxapi.types.attachments.upload import AttachmentPayload, AttachmentUpload
from maxapi.types.input_media import InputMediaBuffer
from maxapi.types.updates.message_callback import MessageForCallback


def _close_created_task_coroutine(coro):
    coro.close()
    return MagicMock()


@pytest.mark.asyncio
async def test_send_callback_processes_input_media_attachment(mock_bot_token):
    bot = Bot(token=mock_bot_token)
    bot.session = AsyncMock()
    media = InputMediaBuffer(buffer=b"image-bytes", filename="img.bin")
    message = MessageForCallback(text="updated")
    message.attachments = [media]  # type: ignore[assignment]

    processed = MagicMock()
    processed.model_dump.return_value = {"type": "image", "payload": {}}

    with (
        patch(
            "maxapi.methods.send_callback.process_input_media",
            new_callable=AsyncMock,
            return_value=processed,
        ) as mock_process,
        patch.object(
            BaseConnection,
            "request",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as mock_request,
    ):
        await SendCallback(
            bot=bot,
            callback_id="cb-1",
            message=message,
        ).fetch()

    mock_process.assert_awaited_once()
    sent_json = mock_request.await_args.kwargs["json"]
    assert sent_json["message"]["attachments"] == [
        {"type": "image", "payload": {}}
    ]


@pytest.mark.asyncio
async def test_send_callback_serializes_attachment_upload_payload(
    mock_bot_token,
):
    bot = Bot(token=mock_bot_token)
    bot.session = AsyncMock()
    upload = AttachmentUpload(
        type=UploadType.IMAGE,
        payload=AttachmentPayload(token="upload-token"),
    )
    message = MessageForCallback(
        text="updated",
        attachments=[
            Attachment(type=AttachmentType.IMAGE, payload=upload),
        ],
    )

    with patch.object(
        BaseConnection,
        "request",
        new_callable=AsyncMock,
        return_value={"ok": True},
    ) as mock_request:
        await SendCallback(
            bot=bot,
            callback_id="cb-1",
            message=message,
        ).fetch()

    sent_json = mock_request.await_args.kwargs["json"]
    assert sent_json["message"]["attachments"] == [
        {"type": "image", "payload": {"token": "upload-token"}}
    ]


@pytest.mark.asyncio
async def test_base_connection_dispatches_raw_response_on_error(
    mock_bot_token,
):
    bot = Bot(token=mock_bot_token)
    bot.dispatcher = SimpleNamespace(handle_raw_response=AsyncMock())
    response = MagicMock()
    response.status = 400
    response.ok = False
    response.json = AsyncMock(return_value={"error": "bad"})
    session = MagicMock()
    session.closed = False
    session.request = AsyncMock(return_value=response)
    bot.session = session

    base = BaseConnection()
    base.bot = bot

    with (
        patch(
            "asyncio.create_task",
            side_effect=_close_created_task_coroutine,
        ) as create_task,
        pytest.raises(MaxApiError),
    ):
        await base.request(
            method=HTTPMethod.GET,
            path="/test",
            is_return_raw=True,
        )

    create_task.assert_called_once()


@pytest.mark.asyncio
async def test_base_connection_dispatches_raw_response_on_success(
    mock_bot_token,
):
    bot = Bot(token=mock_bot_token)
    bot.dispatcher = SimpleNamespace(handle_raw_response=AsyncMock())
    response = MagicMock()
    response.status = 200
    response.ok = True
    response.json = AsyncMock(return_value={"ok": True})
    session = MagicMock()
    session.closed = False
    session.request = AsyncMock(return_value=response)
    bot.session = session

    base = BaseConnection()
    base.bot = bot

    with patch(
        "asyncio.create_task",
        side_effect=_close_created_task_coroutine,
    ) as create_task:
        result = await base.request(
            method=HTTPMethod.GET,
            path="/test",
            is_return_raw=True,
        )

    assert result == {"ok": True}
    create_task.assert_called_once()


@pytest.mark.asyncio
async def test_edit_chat_includes_notify_false_in_payload(mock_bot_token):
    bot = Bot(token=mock_bot_token)
    bot.session = AsyncMock()

    with patch.object(
        BaseConnection,
        "request",
        new_callable=AsyncMock,
        return_value={"chat_id": 1, "type": "chat", "title": "t"},
    ) as mock_request:
        await EditChat(
            bot=bot,
            chat_id=123,
            notify=False,
        ).fetch()

    sent_json = mock_request.await_args.kwargs["json"]
    assert sent_json["notify"] is False


@pytest.mark.asyncio
async def test_edit_chat_raises_when_icon_fields_are_not_mutually_exclusive(
    mock_bot_token,
):
    bot = Bot(token=mock_bot_token)
    bot.session = AsyncMock()
    icon = PhotoAttachmentRequestPayload(url="https://x", token="t")

    with pytest.raises(MaxIconParamsException):
        await EditChat(
            bot=bot,
            chat_id=123,
            icon=icon,
        ).fetch()
