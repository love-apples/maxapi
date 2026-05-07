from unittest.mock import AsyncMock, patch

from maxapi.bot import Bot
from maxapi.connection.base import BaseConnection
from maxapi.enums.upload_type import UploadType
from maxapi.methods.send_callback import SendCallback
from maxapi.types.attachments.buttons.callback_button import CallbackButton
from maxapi.types.attachments.upload import AttachmentPayload, AttachmentUpload
from maxapi.types.updates.message_callback import MessageForCallback
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder


async def test_send_callback_serializes_inline_keyboard_as_attachment(
    mock_bot_token,
):
    bot = Bot(token=mock_bot_token)
    bot.session = AsyncMock()

    keyboard = InlineKeyboardBuilder().row(
        CallbackButton(text="Info", payload="info")
    )
    message = MessageForCallback(
        text="updated",
        attachments=[keyboard.as_markup()],
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
            notification="n",
        ).fetch()

    sent_json = mock_request.await_args.kwargs["json"]
    attachment = sent_json["message"]["attachments"][0]
    assert attachment["type"] == "inline_keyboard"
    assert "payload" in attachment
    assert "buttons" in attachment["payload"]


async def test_send_callback_serializes_direct_attachment_upload(
    mock_bot_token,
):
    bot = Bot(token=mock_bot_token)
    bot.session = AsyncMock()

    message = MessageForCallback(
        text="updated",
        attachments=[
            AttachmentUpload(
                type=UploadType.IMAGE,
                payload=AttachmentPayload(token="upload-token"),
            )
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
