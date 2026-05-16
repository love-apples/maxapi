import pytest
from maxapi.enums.parse_mode import ParseMode
from maxapi.enums.update import UpdateType
from maxapi.types.attachments.attachment import ButtonsPayload
from maxapi.types.attachments.buttons.callback_button import CallbackButton
from maxapi.types.callback import Callback
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
        message: MessageForCallback,
        notification=None,
    ):
        self.last = {
            "callback_id": callback_id,
            "message": message,
            "notification": notification,
        }
        return {"ok": True}


@pytest.fixture
def cb_obj():
    user = User(
        user_id=42, first_name="Test", is_bot=False, last_activity_time=1
    )
    return Callback(timestamp=1, callback_id="cb1", payload=None, user=user)


def test_get_ids_with_no_message(cb_obj):
    mc = MessageCallback(
        message=None,
        user_locale=None,
        callback=cb_obj,
        update_type=UpdateType.MESSAGE_CALLBACK,
        timestamp=1,
    )
    ids = mc.get_ids()
    assert ids[0] is None
    assert ids[1] == 42


async def test_answer_with_no_message_raises_on_change(cb_obj):
    mc = MessageCallback(
        message=None,
        user_locale=None,
        callback=cb_obj,
        update_type=UpdateType.MESSAGE_CALLBACK,
        timestamp=1,
    )
    bot = DummyBot()
    mc.bot = bot

    with pytest.raises(ValueError, match="исходное сообщение отсутствует"):
        await mc.answer(notification="n", new_text="text")


async def test_answer_with_no_message_notification_only(cb_obj):
    mc = MessageCallback(
        message=None,
        user_locale=None,
        callback=cb_obj,
        update_type=UpdateType.MESSAGE_CALLBACK,
        timestamp=1,
    )
    bot = DummyBot()
    mc.bot = bot

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
    from maxapi.enums.chat_type import ChatType
    from maxapi.types.message import Message, MessageBody, Recipient

    recipient = Recipient(chat_id=100, chat_type=ChatType.CHAT)
    body = MessageBody(mid="mid1", seq=1, text="hello")
    message = Message(recipient=recipient, timestamp=1, body=body)

    mc = MessageCallback(
        message=message,
        user_locale=None,
        callback=cb_obj,
        update_type=UpdateType.MESSAGE_CALLBACK,
        timestamp=1,
    )
    bot = DummyBot(parse_mode=ParseMode.MARKDOWN)
    mc.bot = bot

    await mc.answer(new_text="world")

    assert bot.last["message"] is not None
    assert bot.last["message"].format == ParseMode.MARKDOWN


async def test_answer_explicit_format_overrides_bot_default(cb_obj):
    """Явно переданный format перекрывает parse_mode бота."""
    from maxapi.enums.chat_type import ChatType
    from maxapi.types.message import Message, MessageBody, Recipient

    recipient = Recipient(chat_id=100, chat_type=ChatType.CHAT)
    body = MessageBody(mid="mid2", seq=2, text="hello")
    message = Message(recipient=recipient, timestamp=1, body=body)

    mc = MessageCallback(
        message=message,
        user_locale=None,
        callback=cb_obj,
        update_type=UpdateType.MESSAGE_CALLBACK,
        timestamp=1,
    )
    bot = DummyBot(parse_mode=ParseMode.MARKDOWN)
    mc.bot = bot

    await mc.answer(new_text="world", format=ParseMode.HTML)

    assert bot.last["message"].format == ParseMode.HTML


async def test_edit_allows_overriding_attachments(cb_obj):
    from maxapi.enums.chat_type import ChatType
    from maxapi.types.message import Message, MessageBody, Recipient

    recipient = Recipient(chat_id=100, chat_type=ChatType.CHAT)
    body = MessageBody(mid="mid3", seq=3, text="hello")
    message = Message(recipient=recipient, timestamp=1, body=body)

    mc = MessageCallback(
        message=message,
        user_locale=None,
        callback=cb_obj,
        update_type=UpdateType.MESSAGE_CALLBACK,
        timestamp=1,
    )
    bot = DummyBot(parse_mode=ParseMode.MARKDOWN)
    mc.bot = bot

    await mc.edit(text="world", attachments=[])

    assert bot.last["message"] is not None
    assert bot.last["message"].attachments == []


async def test_edit_accepts_inline_keyboard_attachment(cb_obj):
    from maxapi.enums.chat_type import ChatType
    from maxapi.types.message import Message, MessageBody, Recipient

    recipient = Recipient(chat_id=100, chat_type=ChatType.CHAT)
    body = MessageBody(mid="mid4", seq=4, text="hello")
    message = Message(recipient=recipient, timestamp=1, body=body)

    mc = MessageCallback(
        message=message,
        user_locale=None,
        callback=cb_obj,
        update_type=UpdateType.MESSAGE_CALLBACK,
        timestamp=1,
    )
    bot = DummyBot(parse_mode=ParseMode.MARKDOWN)
    mc.bot = bot

    keyboard = InlineKeyboardBuilder().row(
        CallbackButton(text="Info", payload="info")
    )

    await mc.edit(text="world", attachments=[keyboard.as_markup()])

    assert bot.last["message"] is not None
    assert len(bot.last["message"].attachments or []) == 1
