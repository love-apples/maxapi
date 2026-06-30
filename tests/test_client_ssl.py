"""Тесты SSL-настроек aiohttp-клиента."""

from maxapi.client.ssl import connector_kwargs, with_default_connector


def test_with_default_connector_preserves_custom_connector():
    """Пользовательский connector не заменяется."""
    connector = object()

    result = with_default_connector({"connector": connector})

    assert result == {"connector": connector}


def test_connector_kwargs_does_not_leak_session_kwargs():
    """Для временной сессии возвращается только connector."""
    connector = object()

    result = connector_kwargs(
        {"connector": connector, "raise_for_status": True}
    )

    assert result == {"connector": connector}
