from maxapi.utils.vcf import VcfInfo, parse_vcf_info


def test_parse_vcf_info_full():
    vcf = (
        "BEGIN:VCARD\r\n"
        "VERSION:3.0\r\n"
        "PRODID:ez-vcard 0.10.3\r\n"
        "TEL;TYPE=cell:70000000000\r\n"
        "FN:Тестовый Пользователь\r\n"
        "END:VCARD\r\n"
    )
    info = parse_vcf_info(vcf)
    assert isinstance(info, VcfInfo)
    assert info.full_name == "Тестовый Пользователь"
    assert info.phone == "70000000000"
    assert info.phones == ("70000000000",)
    assert info.fields["VERSION"] == ("3.0",)
    assert info.fields["PRODID"] == ("ez-vcard 0.10.3",)


def test_parse_vcf_info_missing_fields_ok():
    vcf = "BEGIN:VCARD\r\nVERSION:3.0\r\nEND:VCARD\r\n"
    info = parse_vcf_info(vcf)
    assert info.full_name is None
    assert info.phone is None
    assert info.phones == ()
    assert info.fields["VERSION"] == ("3.0",)


def test_parse_vcf_info_empty_string():
    info = parse_vcf_info("")
    assert info.full_name is None
    assert info.phones == ()
    assert info.fields == {}
