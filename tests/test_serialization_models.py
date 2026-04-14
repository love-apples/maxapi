import json

from maxapi.enums.attachment import AttachmentType
from maxapi.enums.chat_type import ChatType
from maxapi.enums.text_style import TextStyle
from maxapi.types import CallbackButton, ClipboardButton, LinkButton
from maxapi.types.attachments.attachment import (
    Attachment,
    ButtonsPayload,
    OtherAttachmentPayload,
    PhotoAttachmentPayload,
    ShareAttachmentPayload,
)
from maxapi.types.attachments.file import File
from maxapi.types.attachments.share import Share
from maxapi.types.message import (
    MarkupElement,
    Message,
    MessageBody,
    Messages,
    Recipient,
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


def test_share_attachment_payload_deserialize():
    """
    Регрессия для #108: входящий attachment с type="share" должен
    десериализоваться как Share с payload типа ShareAttachmentPayload,
    чтобы пользователь мог pattern-match на ShareAttachmentPayload,
    а не получать OtherAttachmentPayload (который "для файлов").
    """
    body = MessageBody.model_validate(
        {
            "mid": "mid.test",
            "seq": 1,
            "attachments": [
                {
                    "type": "share",
                    "payload": {
                        "url": "https://max.ru/c/x/AZ2I.bkQ",
                        "token": "f9LHodD0cOL",
                    },
                    "title": "Title",
                    "description": "Desc",
                    "image_url": "https://i.oneme.ru/i?r=abc",
                }
            ],
        }
    )

    att = body.attachments[0]
    assert isinstance(att, Share)
    assert att.title == "Title"
    assert att.description == "Desc"
    assert att.image_url == "https://i.oneme.ru/i?r=abc"
    assert isinstance(att.payload, ShareAttachmentPayload)
    assert att.payload.url == "https://max.ru/c/x/AZ2I.bkQ"
    assert att.payload.token == "f9LHodD0cOL"


def test_file_attachment_payload_unchanged_by_share_fix():
    """
    Страховка: после добавления ShareAttachmentPayload файл-вложение
    продолжает десериализовываться как File c OtherAttachmentPayload
    (не перехватывается ShareAttachmentPayload-классом).
    """
    body = MessageBody.model_validate(
        {
            "mid": "mid.test",
            "seq": 1,
            "attachments": [
                {
                    "type": "file",
                    "payload": {
                        "url": "https://fd.oneme.ru/some/file",
                        "token": "filetok",
                    },
                    "filename": "doc.pdf",
                    "size": 1024,
                }
            ],
        }
    )

    att = body.attachments[0]
    assert isinstance(att, File)
    assert isinstance(att.payload, OtherAttachmentPayload)
    assert att.payload.url == "https://fd.oneme.ru/some/file"


def test_buttons_payload_deserialize_uses_button_type_discriminator():
    payload = ButtonsPayload.model_validate(
        {
            "buttons": [
                [
                    {
                        "type": "clipboard",
                        "text": "Copy",
                        "payload": "copied text",
                    }
                ],
                [
                    {
                        "type": "callback",
                        "text": "Callback",
                        "payload": "callback_payload",
                    },
                    {
                        "type": "link",
                        "text": "Docs",
                        "url": "https://example.com",
                    },
                ],
            ]
        }
    )

    assert isinstance(payload.buttons[0][0], ClipboardButton)
    assert isinstance(payload.buttons[1][0], CallbackButton)
    assert isinstance(payload.buttons[1][1], LinkButton)


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
