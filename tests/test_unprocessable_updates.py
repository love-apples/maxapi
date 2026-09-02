"""Тесты пропуска событий, которые не удалось разобрать.

События с неизвестным типом, а также известным типом, но без
обязательных полей, должны пропускаться без исключений; в лог
при этом должно попадать соответствующее предупреждение.
"""

from unittest.mock import MagicMock

from maxapi.methods.types.getted_updates import (
    _dump_event_json,
    process_update_request,
)


def test_dump_event_json_fallback_on_unserializable_event():
    """При циклических ссылках в событии json.dumps падает даже
    с default=str — должен срабатывать fallback на str().
    """
    event: dict = {"update_type": "bot_started"}
    event["self"] = event

    assert _dump_event_json(event) == str(event)


async def test_message_created_without_message_is_skipped(caplog):
    """message_created без тела сообщения сопровождается
    предупреждением о неподдерживаемом сообщении на стороне MAX,
    а не о неизвестном типе.
    """
    # Реальный кейс: голосовое сообщение боту приходит апдейтом
    # message_created без поля message.
    bot = MagicMock()
    data = {
        "updates": [
            {
                "timestamp": 1787423104297,
                "user_locale": "ru",
                "update_type": "message_created",
            }
        ],
        "marker": 95412,
    }

    result = await process_update_request(data, bot)

    assert result == []
    assert "неизвестный тип" not in caplog.text
    assert "неподдерживаемое сообщение" in caplog.text
    assert "partner_support@max.ru" in caplog.text


async def test_known_update_type_with_missing_fields_is_skipped(caplog):
    """Известный тип события без обязательных полей пропускается
    с предупреждением, направляющим в issue проекта, и JSON-payload
    для приложения к issue.
    """
    bot = MagicMock()
    # bot_started без обязательного поля user
    data = {
        "updates": [
            {
                "timestamp": 1787423104297,
                "chat_id": 95412,
                "update_type": "bot_started",
            }
        ],
        "marker": 95412,
    }

    result = await process_update_request(data, bot)

    assert result == []
    assert "github.com/love-apples/maxapi/issues" in caplog.text
    # Кейс message_created без тела сюда попадать не должен:
    # у него отдельное сообщение про поддержку MAX
    assert "partner_support@max.ru" not in caplog.text
    assert "неизвестный тип" not in caplog.text
    # JSON события должен попасть в лог для отправки в поддержку
    assert '"chat_id": 95412' in caplog.text
    assert '"update_type": "bot_started"' in caplog.text


async def test_unknown_update_type_logged_as_unknown(caplog):
    """Неизвестный тип события сопровождается предупреждением
    UNKNOWN_UPDATE_DISCLAIMER и не ломает обработку остальных
    событий.
    """
    bot = MagicMock()
    data = {
        "updates": [
            {
                "timestamp": 1787423104297,
                "user_locale": "ru",
                "update_type": "unknown_event_123",
            }
        ],
        "marker": 95412,
    }

    result = await process_update_request(data, bot)

    assert result == []
    assert "неизвестный тип обновления" in caplog.text
    assert "unknown_event_123" in caplog.text
