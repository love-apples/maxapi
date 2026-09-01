from unittest.mock import AsyncMock, Mock, patch

from maxapi.connection.base import BaseConnection
from maxapi.methods.send_message import SendMessage
from maxapi.types.attachments.buttons.callback_button import CallbackButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder


async def test_send_message_fetch_skips_empty_inline_keyboard(bot):
    method = SendMessage(
        bot=bot,
        chat_id=1,
        attachments=[
            InlineKeyboardBuilder().as_markup(),
            InlineKeyboardBuilder()
            .row(CallbackButton(text="ok", payload="payload"))
            .as_markup(),
        ],
    )

    with patch.object(
        BaseConnection, "request", new=AsyncMock(return_value=Mock())
    ) as mocked_request:
        await method.fetch()

    attachments = mocked_request.call_args.kwargs["json"]["attachments"]
    assert len(attachments) == 1
    assert attachments[0]["type"] == "inline_keyboard"
    assert attachments[0]["payload"]["buttons"][0][0]["text"] == "ok"


async def test_send_message_fetch_puts_disable_link_preview_in_params(bot):
    """disable_link_preview уходит в query как "true"/"false"."""
    method = SendMessage(
        bot=bot, chat_id=1, text="t", disable_link_preview=True
    )

    with patch.object(
        BaseConnection, "request", new=AsyncMock(return_value=Mock())
    ) as mocked_request:
        await method.fetch()

    kwargs = mocked_request.call_args.kwargs
    assert kwargs["params"]["disable_link_preview"] == "true"
    assert "disable_link_preview" not in kwargs["json"]
