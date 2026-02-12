import pytest

from maxapi.types.updates.message_callback import MessageCallback, MessageForCallback
from maxapi.types.callback import Callback
from maxapi.types.users import User
from maxapi.enums.update import UpdateType


class DummyBot:
    def __init__(self):
        self.last = {}

    def _ensure_bot(self):
        return self

    async def send_callback(self, callback_id: str, message: MessageForCallback,
                            notification=None):
        self.last = {
            "callback_id": callback_id,
            "message": message,
            "notification": notification,
        }
        return {"ok": True}


@pytest.fixture
def cb_obj():
    user = User(user_id=42, first_name="Test", is_bot=False, last_activity_time=1)
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


async def test_answer_with_no_message(cb_obj):
    mc = MessageCallback(
        message=None,
        user_locale=None,
        callback=cb_obj,
        update_type=UpdateType.MESSAGE_CALLBACK,
        timestamp=1,
    )
    bot = DummyBot()
    mc.bot = bot

    res = await mc.answer(notification="n", new_text="text")
    assert res == {"ok": True}
    assert bot.last["callback_id"] == "cb1"
    assert bot.last["message"].text == "text"
    assert bot.last["notification"] == "n"
