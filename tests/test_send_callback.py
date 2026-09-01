from unittest.mock import AsyncMock, patch

import pytest
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


async def test_send_callback_omits_attachments_when_not_provided(
    mock_bot_token,
):
    bot = Bot(token=mock_bot_token)
    bot.session = AsyncMock()
    message = MessageForCallback(text="updated")

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
    assert "attachments" not in sent_json["message"]


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


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, "true"), (False, "false")],
)
async def test_send_callback_puts_disable_link_preview_in_params(
    mock_bot_token,
    value,
    expected,
):
    """disable_link_preview уходит в query-параметры, а не в тело."""
    bot = Bot(token=mock_bot_token)
    bot.session = AsyncMock()

    message = MessageForCallback(text="updated")

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
            disable_link_preview=value,
        ).fetch()

    kwargs = mock_request.await_args.kwargs
    assert kwargs["params"]["disable_link_preview"] == expected
    assert "disable_link_preview" not in kwargs["json"]
    assert "disable_link_preview" not in kwargs["json"]["message"]


async def test_send_callback_omits_disable_link_preview_when_none(
    mock_bot_token,
):
    """Без явного значения ключа в params нет."""
    bot = Bot(token=mock_bot_token)
    bot.session = AsyncMock()

    with patch.object(
        BaseConnection,
        "request",
        new_callable=AsyncMock,
        return_value={"ok": True},
    ) as mock_request:
        await SendCallback(
            bot=bot,
            callback_id="cb-1",
            message=MessageForCallback(text="updated"),
        ).fetch()

    assert (
        "disable_link_preview" not in mock_request.await_args.kwargs["params"]
    )


async def test_bot_send_callback_passes_explicit_disable_link_preview(
    mock_bot_token,
):
    """Явный флаг доходит до SendCallback."""
    bot = Bot(token=mock_bot_token)
    bot.session = AsyncMock()

    with patch.object(
        BaseConnection,
        "request",
        new_callable=AsyncMock,
        return_value={"ok": True},
    ) as mock_request:
        await bot.send_callback(
            callback_id="cb-1",
            disable_link_preview=True,
        )

    params = mock_request.await_args.kwargs["params"]
    assert params["disable_link_preview"] == "true"


async def test_bot_send_callback_uses_bot_default_disable_link_preview(
    mock_bot_token,
):
    """Без явного значения берётся дефолт бота."""
    bot = Bot(token=mock_bot_token, disable_link_preview=True)
    bot.session = AsyncMock()

    with patch.object(
        BaseConnection,
        "request",
        new_callable=AsyncMock,
        return_value={"ok": True},
    ) as mock_request:
        await bot.send_callback(callback_id="cb-1")

    params = mock_request.await_args.kwargs["params"]
    assert params["disable_link_preview"] == "true"
