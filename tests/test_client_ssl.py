"""Тесты SSL-настроек aiohttp-клиента."""

from aiohttp import TCPConnector
from maxapi.client.ssl import connector_kwargs, with_default_connector


def test_with_default_connector_preserves_custom_connector():
    """Пользовательский connector не заменяется и не переходит в владение."""
    connector = object()

    result = with_default_connector({"connector": connector})

    assert result["connector"] is connector
    assert result["connector_owner"] is False


def test_with_default_connector_ignores_explicit_owner():
    """Явный connector_owner=True не даёт сессии закрыть чужой connector.

    Сессия бота пересоздаётся поверх того же коннектора, поэтому
    передача владения ей означала бы смерть коннектора после первого
    close_session().
    """
    connector = object()

    result = with_default_connector(
        {"connector": connector, "connector_owner": True}
    )

    assert result["connector"] is connector
    assert result["connector_owner"] is False


def test_connector_kwargs_ignores_explicit_owner():
    """Временная сессия не забирает владение даже по явной просьбе."""
    connector = object()

    result = connector_kwargs(
        {"connector": connector, "connector_owner": True}
    )

    assert result == {"connector": connector, "connector_owner": False}


async def test_with_default_connector_owns_created_connector():
    """Собственный дефолтный connector закрывается сессией."""
    result = with_default_connector({})

    assert isinstance(result["connector"], TCPConnector)
    assert result["connector_owner"] is True

    await result["connector"].close()


async def test_with_default_connector_does_not_mutate_source():
    """Исходный словарь kwargs не изменяется."""
    kwargs: dict = {}

    result = with_default_connector(kwargs)

    assert kwargs == {}

    await result["connector"].close()


def test_connector_kwargs_does_not_leak_session_kwargs():
    """Для временной сессии возвращается только connector и владелец."""
    connector = object()

    result = connector_kwargs(
        {"connector": connector, "raise_for_status": True}
    )

    assert result == {"connector": connector, "connector_owner": False}


async def test_connector_kwargs_owns_created_connector():
    """Временная сессия закрывает созданный ею дефолтный connector."""
    result = connector_kwargs({})

    assert isinstance(result["connector"], TCPConnector)
    assert result["connector_owner"] is True

    await result["connector"].close()
