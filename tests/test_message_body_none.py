import pytest
from maxapi.enums.chat_type import ChatType
from maxapi.types.message import Message, Recipient
from maxapi.types.users import User


@pytest.fixture
def recipient():
    return Recipient(user_id=1, chat_id=2, chat_type=ChatType.DIALOG)


def make_message_with_no_body(recipient):
    user = User(
        user_id=10, first_name="Test", is_bot=False, last_activity_time=1
    )
    return Message(sender=user, recipient=recipient, timestamp=1, body=None)


def test_reply_raises_when_body_none(recipient):
    msg = make_message_with_no_body(recipient)

    with pytest.raises(ValueError, match="поле body отсутствует"):
        msg.reply()


def test_forward_raises_when_body_none(recipient):
    msg = make_message_with_no_body(recipient)

    with pytest.raises(ValueError, match="поле body отсутствует"):
        msg.forward(chat_id=3)


def test_edit_raises_when_body_none(recipient):
    msg = make_message_with_no_body(recipient)

    with pytest.raises(ValueError, match="поле body отсутствует"):
        msg.edit(text="x")


def test_delete_raises_when_body_none(recipient):
    msg = make_message_with_no_body(recipient)

    with pytest.raises(ValueError, match="поле body отсутствует"):
        msg.delete()


def test_pin_raises_when_body_none(recipient):
    msg = make_message_with_no_body(recipient)

    with pytest.raises(ValueError, match="поле body отсутствует"):
        msg.pin()
