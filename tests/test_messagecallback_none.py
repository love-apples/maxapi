from __future__ import annotations

import pytest
from maxapi.enums.chat_type import ChatType
from maxapi.enums.parse_mode import ParseMode
from maxapi.enums.update import UpdateType
from maxapi.types.attachments.attachment import ButtonsPayload
from maxapi.types.attachments.buttons.callback_button import CallbackButton
from maxapi.types.callback import Callback
from maxapi.types.message import Message, MessageBody, Recipient
from maxapi.types.updates.message_callback import (
    MessageCallback,
    MessageForCallback,
)
from maxapi.types.users import User
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from pydantic import ValidationError


class DummyBot:
    def __init__(self, parse_mode=None):
        self.last = {}
        self.parse_mode = parse_mode

    def _ensure_bot(self):
        return self

    def resolve_format(self, format, parse_mode=None):
        """Упрощённая копия Bot.resolve_format для тестов."""
        if format is not None:
            return format
        if parse_mode is not None:
            return parse_mode
        return self.parse_mode

    async def send_callback(
        self,
        callback_id: str,
        message: MessageForCallback | None = None,
        notification=None,
        *,
        disable_link_preview=None,
    ):
        self.last = {
            "callback_id": callback_id,
            "message": message,
            "notification": notification,
            "disable_link_preview": disable_link_preview,
        }
        return {"ok": True}


def _make_callback(
    cb_obj,
    *,
    message=None,
    parse_mode=None,
) -> tuple[MessageCallback, DummyBot]:
    """Собирает MessageCallback с привязанным DummyBot."""
    mc = MessageCallback(
        message=message,
        user_locale=None,
        callback=cb_obj,
        update_type=UpdateType.MESSAGE_CALLBACK,
        timestamp=1,
    )
    bot = DummyBot(parse_mode=parse_mode)
    mc.bot = bot
    return mc, bot


def _make_message(mid: str, text: str = "hello") -> Message:
    """Собирает минимальное сообщение для callback-тестов."""
    recipient = Recipient(chat_id=100, chat_type=ChatType.CHAT)
    body = MessageBody(mid=mid, seq=1, text=text)
    return Message(recipient=recipient, timestamp=1, body=body)


@pytest.fixture
def cb_obj():
    user = User(
        user_id=42, first_name="Test", is_bot=False, last_activity_time=1
    )
    return Callback(timestamp=1, callback_id="cb1", payload=None, user=user)


def test_get_ids_with_no_message(cb_obj):
    mc, _ = _make_callback(cb_obj)
    ids = mc.get_ids()
    assert ids[0] is None
    assert ids[1] == 42


async def test_answer_with_no_message_raises_on_change(cb_obj):
    mc, _ = _make_callback(cb_obj)

    with pytest.raises(ValueError, match="исходное сообщение отсутствует"):
        await mc.answer(notification="n", new_text="text")


async def test_edit_with_no_message_raises_on_attachments_change(cb_obj):
    mc, _ = _make_callback(cb_obj)

    with pytest.raises(ValueError, match="исходное сообщение отсутствует"):
        await mc.edit(attachments=[])


async def test_answer_with_no_message_notification_only(cb_obj):
    mc, bot = _make_callback(cb_obj)

    res = await mc.answer(notification="n")
    assert res == {"ok": True}
    assert bot.last["callback_id"] == "cb1"
    assert bot.last["message"] is None
    assert bot.last["notification"] == "n"


def test_message_for_callback_rejects_bare_payload_attachment():
    with pytest.raises(ValidationError):
        MessageForCallback(
            text="updated",
            attachments=[ButtonsPayload(buttons=[])],  # type: ignore[list-item]
        )


async def test_answer_uses_bot_default_parse_mode(cb_obj):
    """Если format не передан явно, берётся parse_mode из бота."""
    mc, bot = _make_callback(
        cb_obj,
        message=_make_message("mid1"),
        parse_mode=ParseMode.MARKDOWN,
    )

    await mc.answer(new_text="world")

    assert bot.last["message"] is not None
    assert bot.last["message"].format == ParseMode.MARKDOWN


async def test_answer_explicit_format_overrides_bot_default(cb_obj):
    """Явно переданный format перекрывает parse_mode бота."""
    mc, bot = _make_callback(
        cb_obj,
        message=_make_message("mid2"),
        parse_mode=ParseMode.MARKDOWN,
    )

    await mc.answer(new_text="world", format=ParseMode.HTML)

    assert bot.last["message"].format == ParseMode.HTML


async def test_edit_allows_overriding_attachments(cb_obj):
    mc, bot = _make_callback(
        cb_obj,
        message=_make_message("mid3"),
        parse_mode=ParseMode.MARKDOWN,
    )

    await mc.edit(text="world", attachments=[])

    assert bot.last["message"] is not None
    assert bot.last["message"].attachments == []


async def test_edit_accepts_inline_keyboard_attachment(cb_obj):
    mc, bot = _make_callback(
        cb_obj,
        message=_make_message("mid4"),
        parse_mode=ParseMode.MARKDOWN,
    )

    keyboard = InlineKeyboardBuilder().row(
        CallbackButton(text="Info", payload="info")
    )

    await mc.edit(text="world", attachments=[keyboard.as_markup()])

    assert bot.last["message"] is not None
    assert len(bot.last["message"].attachments or []) == 1


async def test_answer_passes_disable_link_preview(cb_obj):
    """answer прокидывает disable_link_preview в bot.send_callback."""
    mc, bot = _make_callback(cb_obj, message=_make_message("mid-dlp"))

    await mc.answer(new_text="world", disable_link_preview=True)

    assert bot.last["disable_link_preview"] is True


async def test_edit_passes_disable_link_preview(cb_obj):
    """edit прокидывает disable_link_preview в bot.send_callback."""
    mc, bot = _make_callback(cb_obj, message=_make_message("mid-dlp2"))

    await mc.edit(text="world")
    assert bot.last["disable_link_preview"] is None

    await mc.edit(text="world", disable_link_preview=True)
    assert bot.last["disable_link_preview"] is True
