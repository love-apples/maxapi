from unittest.mock import AsyncMock, Mock, patch

import pytest
from maxapi.connection.base import BaseConnection
from maxapi.methods.send_message import SendMessage
from maxapi.types.attachments.buttons.callback_button import CallbackButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder


@pytest.mark.asyncio
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
