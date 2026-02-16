import json

from maxapi.enums.attachment import AttachmentType
from maxapi.enums.chat_type import ChatType
from maxapi.enums.text_style import TextStyle
from maxapi.types.attachments.attachment import (
    Attachment,
    PhotoAttachmentPayload,
)
from maxapi.types.message import (
    Message,
    MessageBody,
    Recipient,
    MarkupElement,
    Messages,
)
from maxapi.types.users import User


def make_simple_message(fake_user, faker) -> Message:
    user_data = fake_user()
    sender = User(**user_data)

    recipient = Recipient(
        user_id=None,
        chat_id=faker.random_int(min=1, max=10000),
        chat_type=ChatType.CHAT,
    )
    body = MessageBody(
        mid=faker.uuid4(),
        seq=faker.random_int(min=1, max=1000),
        text=faker.sentence(),
    )
    msg = Message(
        sender=sender,
        recipient=recipient,
        timestamp=int(faker.date_time().timestamp()),
        body=body,
    )
    return msg


def test_message_serialize_deserialize_roundtrip(fake_user, faker):
    msg = make_simple_message(fake_user, faker)

    # сериализуем модель в словарь (Pydantic v2)
    d = msg.model_dump()

    # убедиться, что поле bot исключено из дампа
    assert "bot" not in d

    # сериализация в JSON и обратная десериализация
    j = json.dumps(d)
    parsed = json.loads(j)

    # восстановление модели из десериализованных данных
    msg2 = Message.model_validate(parsed)

    assert msg2.sender.user_id == msg.sender.user_id
    assert msg2.recipient.chat_id == msg.recipient.chat_id
    assert msg2.body.mid == msg.body.mid
    assert msg2.timestamp == msg.timestamp


def test_attachment_serialize_deserialize(faker):
    payload = PhotoAttachmentPayload(
        photo_id=faker.random_int(min=1, max=100),
        token=faker.uuid4(),
        url=faker.url(),
    )
    att = Attachment(type=AttachmentType.IMAGE, payload=payload)

    d = att.model_dump()
    j = json.dumps(d)
    att2 = Attachment.model_validate(json.loads(j))

    assert att2.type == att.type
    assert isinstance(att2.payload, PhotoAttachmentPayload)
    assert att2.payload.photo_id == payload.photo_id


def test_markup_element_alias_and_serialization(faker):
    mk = MarkupElement(type=TextStyle.STRONG, from_=0, length=4)
    d = mk.model_dump(by_alias=True)
    # в дампе должно присутствовать поле 'from' (алиас для from_)
    assert "from" in d
    assert d["from"] == 0

    mk2 = MarkupElement.model_validate(d)
    assert mk2.from_ == mk.from_


def test_messages_list_serialization(fake_user, faker):
    msg = make_simple_message(fake_user, faker)
    msgs = Messages(messages=[msg])
    d = msgs.model_dump()
    assert isinstance(d["messages"], list)
    assert d["messages"][0]["body"]["mid"] == msg.body.mid
