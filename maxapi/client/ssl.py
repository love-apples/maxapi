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
    """Добавить connector по умолчанию, если он не задан явно.

    Пользовательский коннектор переиспользуется всеми сессиями бота и
    переживает их пересоздание, поэтому владельцем остаётся
    пользователь: ``connector_owner`` принудительно выставляется в
    ``False``, и ``ClientSession.close()`` чужой коннектор не трогает.
    Переданный пользователем ``connector_owner=True`` игнорируется —
    он означал бы, что первый же ``close_session()`` закрывает
    коннектор, который затем переиспользует следующая сессия.

    Собственный дефолтный коннектор создаётся под каждую сессию, и
    закрыть его сессия обязана: ``connector_owner=True``.

    Явный ``connector=None`` — принятый в aiohttp способ попросить
    коннектор по умолчанию — равносилен отсутствию ключа: подставляем
    свой, с доверенным CA. Оставить ``None`` нельзя: aiohttp создал бы
    коннектор сам, и при ``connector_owner=False`` его никто никогда
    не закрыл бы.

    Args:
        kwargs: Пользовательские параметры ``ClientSession``.

    Returns:
        Копия ``kwargs`` с проставленными ``connector`` и
        ``connector_owner``.
    """

    session_kwargs = dict(kwargs)
    if session_kwargs.get("connector") is not None:
        session_kwargs["connector_owner"] = False
    else:
        session_kwargs["connector"] = create_default_connector()
        session_kwargs["connector_owner"] = True
    return session_kwargs


def connector_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Вернуть connector и его владельца для временной aiohttp-сессии.

    Временная сессия живёт один вызов, поэтому пользовательский
    коннектор она не закрывает никогда — ``connector_owner=False``
    независимо от того, что передал пользователь. Созданный на месте
    дефолтный коннектор, наоборот, закрыть больше некому.

    Явный ``connector=None`` равносилен отсутствию ключа — см.
    :func:`with_default_connector`.

    Args:
        kwargs: Пользовательские параметры ``ClientSession``.

    Returns:
        Словарь с ключами ``connector`` и ``connector_owner``.
    """

    connector = kwargs.get("connector")
    if connector is not None:
        return {
            "connector": connector,
            "connector_owner": False,
        }
    return {"connector": create_default_connector(), "connector_owner": True}
