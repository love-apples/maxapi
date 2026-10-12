"""Вложения неизвестного типа (например, опросы) не ломают разбор."""

import pytest
from maxapi.types.attachments import Location, UnknownAttachment
from maxapi.types.message import MessageBody
from pydantic import ValidationError

POLL = {
    "type": "poll",
    "payload": {"question": "Куда идём?", "answers": ["A", "B"]},
    "poll_id": 42,
}


def _body(*attachments):
    return MessageBody.model_validate(
        {"mid": "m", "seq": 1, "text": "голосуем", "attachments": attachments}
    )


def test_unknown_type_is_kept_as_is():
    body = _body(POLL, {"type": "location", "latitude": 1, "longitude": 2})

    poll, location = body.attachments
    assert isinstance(poll, UnknownAttachment)
    assert poll.payload == POLL["payload"]
    assert poll.model_dump() == POLL
    assert isinstance(location, Location)
    assert body.text == "голосуем"


def test_known_type_with_bad_payload_still_fails():
    with pytest.raises(ValidationError):
        _body({"type": "location", "latitude": "not-a-number"})
