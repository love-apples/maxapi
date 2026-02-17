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


async def test_reply_raises_when_body_none(recipient):
    msg = make_message_with_no_body(recipient)

    with pytest.raises(ValueError):
        await msg.reply()


async def test_forward_raises_when_body_none(recipient):
    msg = make_message_with_no_body(recipient)

    with pytest.raises(ValueError):
        await msg.forward(chat_id=3)


async def test_edit_raises_when_body_none(recipient):
    msg = make_message_with_no_body(recipient)

    with pytest.raises(ValueError):
        await msg.edit(text="x")


async def test_delete_raises_when_body_none(recipient):
    msg = make_message_with_no_body(recipient)

    with pytest.raises(ValueError):
        await msg.delete()


async def test_pin_raises_when_body_none(recipient):
    msg = make_message_with_no_body(recipient)

    with pytest.raises(ValueError):
        await msg.pin()
