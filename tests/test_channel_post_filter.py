from maxapi.enums.chat_type import ChatType
from maxapi.filters.channel_post import ChannelPostFilter
from maxapi.types import MessageCreated


def test_channel_post_filter_true_for_channel_message():
    event = MessageCreated.model_validate(
        {
            "update_type": "message_created",
            "timestamp": 1,
            "message": {
                "recipient": {"chat_type": "channel", "chat_id": 1},
                "timestamp": 1,
                "body": {"mid": "m1", "seq": 1, "text": "hi"},
            },
        }
    )

    assert event.message.recipient.chat_type == ChatType.CHANNEL
    assert ChannelPostFilter()(event) is True


def test_channel_post_filter_false_for_non_channel_message():
    event = MessageCreated.model_validate(
        {
            "update_type": "message_created",
            "timestamp": 1,
            "message": {
                "recipient": {"chat_type": "chat", "chat_id": 1},
                "timestamp": 1,
                "body": {"mid": "m1", "seq": 1, "text": "hi"},
            },
        }
    )

    assert ChannelPostFilter()(event) is False
