from __future__ import annotations

import pytest
from maxapi.utils.deep_linking import (
    create_deep_link,
    create_start_link,
    create_startapp_link,
    decode_payload,
    encode_payload,
)


def test_encode_payload_example_roundtrip() -> None:
    encoded = encode_payload("123456789")

    assert encoded == "MTIzNDU2Nzg5"
    assert decode_payload(encoded) == "123456789"


def test_unicode_payload_roundtrip() -> None:
    payload = "привет MAX"

    assert decode_payload(encode_payload(payload)) == payload


def test_encode_payload_coerces_non_string_payload() -> None:
    assert encode_payload(123456789) == "MTIzNDU2Nzg5"


@pytest.mark.parametrize("payload", ["a", "ab", "abc", "abcd"])
def test_decode_payload_restores_missing_padding(payload: str) -> None:
    assert decode_payload(encode_payload(payload)) == payload


def test_decode_payload_invalid_base64_raises() -> None:
    with pytest.raises(ValueError, match="URL-safe base64"):
        decode_payload("!!!")


def test_decode_payload_rejects_not_string_payload() -> None:
    with pytest.raises(TypeError, match="payload"):
        decode_payload(object())  # type: ignore[arg-type]


def test_decode_payload_invalid_base64_with_valid_alphabet_raises() -> None:
    with pytest.raises(ValueError, match="URL-safe base64"):
        decode_payload("A")


def test_decode_payload_invalid_utf8_raises_value_error() -> None:
    with pytest.raises(ValueError, match="URL-safe base64"):
        decode_payload("____")


def test_custom_encoder_decoder_roundtrip() -> None:
    def encoder(data: bytes) -> bytes:
        return data[::-1]

    def decoder(data: bytes) -> bytes:
        return data[::-1]

    encoded = encode_payload("secret", encoder=encoder)

    assert decode_payload(encoded, decoder=decoder) == "secret"


def test_create_start_link_from_username() -> None:
    assert (
        create_start_link("MyBot", "abc") == "https://max.ru/MyBot?start=abc"
    )


def test_create_start_link_normalizes_username_at_sign() -> None:
    assert (
        create_start_link("@MyBot", "abc") == "https://max.ru/MyBot?start=abc"
    )


@pytest.mark.parametrize("username", ["", "   ", "@"])
def test_create_start_link_rejects_empty_username(username: str) -> None:
    with pytest.raises(ValueError, match="username"):
        create_start_link(username, "abc")


@pytest.mark.parametrize(
    "username",
    ["My Bot", "https://max.ru/MyBot", "MyBot?x=1", "My/Bot"],
)
def test_create_start_link_rejects_invalid_username(username: str) -> None:
    with pytest.raises(ValueError, match="username"):
        create_start_link(username, "abc")


def test_create_start_link_rejects_not_string_username() -> None:
    with pytest.raises(TypeError, match="username"):
        create_start_link(object(), "abc")  # type: ignore[arg-type]


def test_create_start_link_accepts_url_safe_payload_without_encode() -> None:
    assert (
        create_start_link("MyBot", "abc_DEF-123")
        == "https://max.ru/MyBot?start=abc_DEF-123"
    )


@pytest.mark.parametrize("payload", ["a/b", "a?b", "a=b"])
def test_invalid_payload_characters_raise(payload: str) -> None:
    with pytest.raises(ValueError, match="encode=True"):
        create_start_link("MyBot", payload)


def test_invalid_payload_without_encode_raises() -> None:
    with pytest.raises(ValueError, match="encode=True"):
        create_start_link("MyBot", "hello world")


def test_non_string_payload_is_coerced() -> None:
    assert (
        create_start_link("MyBot", 123456789)
        == "https://max.ru/MyBot?start=123456789"
    )


def test_encode_true_allows_special_characters() -> None:
    assert (
        create_start_link("MyBot", "hello world", encode=True)
        == "https://max.ru/MyBot?start=aGVsbG8gd29ybGQ"
    )


def test_encoder_in_create_start_link_enables_encoding() -> None:
    def encoder(data: bytes) -> bytes:
        return data[::-1]

    assert (
        create_start_link("MyBot", "abc", encoder=encoder)
        == "https://max.ru/MyBot?start=Y2Jh"
    )


def test_start_payload_limit() -> None:
    assert create_start_link("MyBot", "a" * 128)

    with pytest.raises(ValueError, match="128"):
        create_start_link("MyBot", "a" * 129)


def test_startapp_payload_limit() -> None:
    assert create_startapp_link("MyBot", "a" * 512)

    with pytest.raises(ValueError, match="512"):
        create_startapp_link("MyBot", "a" * 513)


def test_create_startapp_link() -> None:
    assert (
        create_startapp_link("MyBot", "abc")
        == "https://max.ru/MyBot?startapp=abc"
    )


def test_create_startapp_link_without_payload() -> None:
    assert create_startapp_link("MyBot") == "https://max.ru/MyBot?startapp"


def test_start_link_rejects_none_payload() -> None:
    with pytest.raises(ValueError, match="payload"):
        create_start_link("MyBot", None)  # type: ignore[arg-type]


def test_unknown_link_type_raises() -> None:
    with pytest.raises(ValueError, match="link_type"):
        create_deep_link("MyBot", "unknown", "abc")  # type: ignore[arg-type]
