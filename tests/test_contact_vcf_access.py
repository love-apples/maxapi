from maxapi.types.attachments.attachment import ContactAttachmentPayload


def test_contact_attachment_payload_vcf_property():
    vcf = (
        "BEGIN:VCARD\r\n"
        "VERSION:3.0\r\n"
        "PRODID:ez-vcard 0.10.3\r\n"
        "TEL;TYPE=cell:70000000000\r\n"
        "FN:Тестовый Пользователь\r\n"
        "END:VCARD\r\n"
    )
    payload = ContactAttachmentPayload(vcf_info=vcf)
    assert payload.vcf.full_name == "Тестовый Пользователь"
    assert payload.vcf.phone == "70000000000"
