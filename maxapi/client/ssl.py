"""SSL-настройки aiohttp-клиента."""

from __future__ import annotations

import ssl
from pathlib import Path
from typing import Any

from aiohttp import TCPConnector

RUSSIAN_TRUSTED_CA_BUNDLE = Path(__file__).with_name("russiantrustedca.pem")


def create_default_ssl_context() -> ssl.SSLContext:
    """Создать SSL-контекст с доверенным российским CA."""

    ssl_context = ssl.create_default_context()
    ssl_context.load_verify_locations(cafile=RUSSIAN_TRUSTED_CA_BUNDLE)
    return ssl_context


def create_default_connector() -> TCPConnector:
    """Создать TCPConnector с доверенным CA для API MAX."""

    return TCPConnector(ssl=create_default_ssl_context())


def with_default_connector(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Добавить connector по умолчанию, если он не задан явно."""

    session_kwargs = dict(kwargs)
    if "connector" not in session_kwargs:
        session_kwargs["connector"] = create_default_connector()
    return session_kwargs


def connector_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Вернуть только connector для временной aiohttp-сессии."""

    if "connector" in kwargs:
        return {"connector": kwargs["connector"]}
    return {"connector": create_default_connector()}
