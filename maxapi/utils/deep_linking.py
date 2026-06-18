"""Утилиты для создания и декодирования deep links MAX."""

from __future__ import annotations

import base64
import binascii
import re
from typing import TYPE_CHECKING, Literal, Protocol, overload

if TYPE_CHECKING:
    from collections.abc import Callable


class _SupportsStr(Protocol):
    def __str__(self) -> str: ...


DEEPLINK_PAYLOAD_MAX_LENGTH = 128
STARTAPP_PAYLOAD_MAX_LENGTH = 512
MAX_DEEPLINK_HOST = "https://max.ru"
BAD_PAYLOAD_PATTERN = re.compile(r"[^A-Za-z0-9_-]")
BAD_USERNAME_PATTERN = re.compile(r"[^A-Za-z0-9_.-]")

__all__ = [
    "create_deep_link",
    "create_start_link",
    "create_startapp_link",
    "decode_payload",
    "encode_payload",
]


def encode_payload(
    payload: str | _SupportsStr,
    encoder: Callable[[bytes], bytes] | None = None,
) -> str:
    """
    Кодирует payload в URL-safe base64 без padding.

    Args:
        payload: Payload. Значения не строкового типа приводятся к строке.
        encoder: Дополнительный кодировщик байтов.

    Returns:
        Закодированный payload.
    """
    if not isinstance(payload, str):
        payload = str(payload)

    payload_bytes = payload.encode("utf-8")
    if encoder is not None:
        payload_bytes = encoder(payload_bytes)

    return base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")


def decode_payload(
    payload: str,
    decoder: Callable[[bytes], bytes] | None = None,
) -> str:
    """
    Декодирует URL-safe base64 payload.

    Args:
        payload: Закодированный payload.
        decoder: Дополнительный декодировщик байтов.

    Returns:
        Исходная строка payload.
    """
    if not isinstance(payload, str):
        raise TypeError("payload должен быть строкой")

    if BAD_PAYLOAD_PATTERN.search(payload):
        raise ValueError("payload должен быть в URL-safe base64 формате")

    padding_needed = (-len(payload)) % 4
    try:
        payload_bytes = base64.urlsafe_b64decode(
            (payload + "=" * padding_needed).encode("ascii")
        )
    except (binascii.Error, ValueError) as e:
        raise ValueError(
            "payload должен быть в URL-safe base64 формате"
        ) from e

    if decoder is not None:
        payload_bytes = decoder(payload_bytes)

    try:
        return payload_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        raise ValueError(
            "payload должен быть в URL-safe base64 формате"
        ) from e


def create_start_link(
    username: str,
    payload: str | _SupportsStr,
    *,
    encode: bool = False,
    encoder: Callable[[bytes], bytes] | None = None,
) -> str:
    """
    Создаёт deep link для старта бота.

    Args:
        username: Username бота.
        payload: Данные, которые MAX передаст в BotStarted.payload.
            Значения не строкового типа приводятся к строке.
        encode: Кодировать payload через URL-safe base64. При передаче
            encoder кодирование выполняется независимо от значения encode.
        encoder: Дополнительный кодировщик байтов.

    Returns:
        Ссылка вида https://max.ru/<botName>?start=<payload>.
    """
    return create_deep_link(
        username=username,
        link_type="start",
        payload=payload,
        encode=encode,
        encoder=encoder,
    )


def create_startapp_link(
    username: str,
    payload: str | _SupportsStr | None = None,
    *,
    encode: bool = False,
    encoder: Callable[[bytes], bytes] | None = None,
) -> str:
    """
    Создаёт deep link для мини-приложения MAX.

    Args:
        username: Username бота.
        payload: Данные для параметра startapp. Значения не строкового типа
            приводятся к строке. Если не передан, ссылка содержит параметр
            startapp без значения.
        encode: Кодировать payload через URL-safe base64. При передаче
            encoder кодирование выполняется независимо от значения encode.
        encoder: Дополнительный кодировщик байтов.

    Returns:
        Ссылка вида https://max.ru/<botName>?startapp=<payload> или
        https://max.ru/<botName>?startapp без payload.
    """
    return create_deep_link(
        username=username,
        link_type="startapp",
        payload=payload,
        encode=encode,
        encoder=encoder,
    )


@overload
def create_deep_link(
    username: str,
    link_type: Literal["start"],
    payload: str | _SupportsStr,
    *,
    encode: bool = False,
    encoder: Callable[[bytes], bytes] | None = None,
) -> str: ...


@overload
def create_deep_link(
    username: str,
    link_type: Literal["startapp"],
    payload: str | _SupportsStr | None = None,
    *,
    encode: bool = False,
    encoder: Callable[[bytes], bytes] | None = None,
) -> str: ...


def create_deep_link(
    username: str,
    link_type: Literal["start", "startapp"],
    payload: str | _SupportsStr | None = None,
    *,
    encode: bool = False,
    encoder: Callable[[bytes], bytes] | None = None,
) -> str:
    """
    Создаёт deep link MAX.

    Args:
        username: Username бота.
        link_type: Тип ссылки: start или startapp.
        payload: Данные для query-параметра. Значения не строкового типа
            приводятся к строке.
        encode: Кодировать payload через URL-safe base64. При передаче
            encoder кодирование выполняется независимо от значения encode.
        encoder: Дополнительный кодировщик байтов.

    Raises:
        ValueError: Если link_type, username или payload невалидны.

    Returns:
        Deep link MAX.
    """
    if link_type not in ("start", "startapp"):
        raise ValueError('link_type должен быть "start" или "startapp"')

    username = _normalize_username(username)
    if payload is None:
        if link_type == "start":
            raise ValueError("payload обязателен для start deep link")
        return f"{MAX_DEEPLINK_HOST}/{username}?{link_type}"

    if not isinstance(payload, str):
        payload = str(payload)

    if encode or encoder is not None:
        payload = encode_payload(payload, encoder=encoder)

    _validate_payload(payload, link_type)
    return f"{MAX_DEEPLINK_HOST}/{username}?{link_type}={payload}"


def _normalize_username(username: str) -> str:
    if not isinstance(username, str):
        raise TypeError("username должен быть строкой")

    username = username.strip().removeprefix("@")

    if not username:
        raise ValueError("username не должен быть пустым")

    if BAD_USERNAME_PATTERN.search(username):
        raise ValueError(
            "username может содержать только A-Z, a-z, 0-9, _, . и -"
        )

    return username


def _validate_payload(
    payload: str, link_type: Literal["start", "startapp"]
) -> None:
    if BAD_PAYLOAD_PATTERN.search(payload):
        raise ValueError(
            "Некорректный payload. Разрешены только A-Z, a-z, 0-9, "
            "_ и -. Передайте encode=True или закодируйте payload вручную."
        )

    max_length = (
        DEEPLINK_PAYLOAD_MAX_LENGTH
        if link_type == "start"
        else STARTAPP_PAYLOAD_MAX_LENGTH
    )
    if len(payload) > max_length:
        raise ValueError(
            f"Payload для {link_type} должен быть не длиннее "
            f"{max_length} символов."
        )
