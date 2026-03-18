from maxapi.enums.attachment import AttachmentType
from maxapi.enums.chat_type import ChatType
from maxapi.filters.contact import ContactFilter
from maxapi.types.attachments.attachment import ContactAttachmentPayload
from maxapi.types.attachments.contact import Contact
from maxapi.types.message import Message, MessageBody, Recipient
from maxapi.types.updates.message_created import MessageCreated


async def test_contact_filter_matches_message_with_contact_attachment():
    payload = ContactAttachmentPayload(
        vcf_info=(
            "BEGIN:VCARD\r\n"
            "VERSION:3.0\r\n"
            "TEL;TYPE=cell:70000000000\r\n"
            "FN:Тестовый Пользователь\r\n"
            "END:VCARD\r\n"
        )
    )
    contact_att = Contact(type=AttachmentType.CONTACT, payload=payload)

    body = MessageBody(
        mid="m1",
        seq=1,
        text="contact",
        attachments=[contact_att],
        markup=[],
    )
    msg = Message(
        sender=None,
        recipient=Recipient(chat_type=ChatType.DIALOG),
        timestamp=0,
        body=body,
    )
    event = MessageCreated(message=msg, timestamp=0)

    flt = ContactFilter()
    res = await flt(event)
    assert isinstance(res, dict)
    assert "contact" in res
    assert res["contact"].type == AttachmentType.CONTACT
    assert res["contact"].payload.vcf_info


async def test_contact_filter_false_when_no_attachments():
    body = MessageBody(
        mid="m1", seq=1, text="plain", attachments=[], markup=[]
    )
    msg = Message(
        sender=None,
        recipient=Recipient(chat_type=ChatType.DIALOG),
        timestamp=0,
        body=body,
    )
    event = MessageCreated(message=msg, timestamp=0)
    flt = ContactFilter()
    assert await flt(event) is False
