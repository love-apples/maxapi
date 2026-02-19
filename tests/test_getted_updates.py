from unittest.mock import AsyncMock, call, patch

import pytest
from maxapi.methods.types.getted_updates import (
    get_update_model,
    process_update_request,
    process_update_webhook,
)


@pytest.mark.asyncio
async def test_process_update_request_calls_get_update_model_and_returns_list(
    bot,
):
    events = {
        "updates": [
            {"update_type": "message_created", "foo": "bar"},
            {"update_type": "message_callback", "baz": "qux"},
        ]
    }

    # Подготавливаем два значения-эмулятора для возврата
    result1 = object()
    result2 = object()

    async_mock = AsyncMock(side_effect=[result1, result2])

    with patch(
        "maxapi.methods.types.getted_updates.get_update_model", async_mock
    ):
        res = await process_update_request(events, bot)

    assert res == [result1, result2]
    assert async_mock.call_count == 2
    assert async_mock.call_args_list == [
        call(events["updates"][0], bot),
        call(events["updates"][1], bot),
    ]


@pytest.mark.asyncio
async def test_process_update_request_logs_and_skips_unknown_updates(bot, caplog):
    """При неизвестном update_type функция должна залогировать
    предупреждение и пропустить событие.
    """
    events = {"updates": [{"update_type": "unknown_type"}]}

    # Патчим get_update_model, чтобы он возвращал None
    async_mock = AsyncMock(return_value=None)

    with patch(
        "maxapi.methods.types.getted_updates.get_update_model", async_mock
    ):
        caplog.clear()
        caplog.set_level("WARNING")

        res = await process_update_request(events, bot)

    # Должен вернуть пустой список (все события пропущены)
    assert res == []

    # Должно быть предупреждение о неизвестном типе обновления
    logged = [r.message for r in caplog.records]
    assert any("неизвестный тип обновления" in msg.lower() for msg in logged)


@pytest.mark.asyncio
async def test_process_update_request_builds_model_from_event(bot, update):
    """Для каждой фикстуры обновления проверяет, что
    `process_update_request` строит корректную модель.

    Использует `bot.auto_requests = False`, чтобы избежать
    внешних API-вызовов в функции `enrich_event`.
    """
    # Отключаем сетевые вызовы в enrich_event
    bot.auto_requests = False

    # Строим словарь события из модели
    event_dict = update.model_dump()
    # Убеждаемся, что поле update_type — enum
    event_dict["update_type"] = update.update_type

    res = await process_update_request({"updates": [event_dict]}, bot)

    assert isinstance(res, list)
    assert len(res) == 1
    res_obj = res[0]

    # Класс полученной модели должен соответствовать классу фикстуры
    assert isinstance(res_obj, update.__class__)
    assert res_obj.update_type == update.update_type


@pytest.mark.asyncio
async def test_process_update_webhook_builds_model_from_event(bot, update):
    """Для каждой фикстуры обновления проверяет, что
    `process_update_webhook` строит корректную модель.

    Использует `bot.auto_requests = False`, чтобы избежать
    внешних API-вызовов в функции `enrich_event`.
    """
    bot.auto_requests = False

    # Строим JSON события из модели
    event_json = update.model_dump()
    # Убеждаемся, что поле update_type — enum
    event_json["update_type"] = update.update_type

    res_obj = await process_update_webhook(event_json, bot)

    # Класс и тип обновления должны совпадать с фикстурой
    assert isinstance(res_obj, update.__class__)
    assert res_obj.update_type == update.update_type


@pytest.mark.asyncio
async def test_get_update_model_raises_value_error_for_unknown_type(bot):
    """Проверяет, что get_update_model возвращает None при
    неизвестном значении update_type (новая логика).
    """
    event = {"update_type": "unknown_type"}

    res = await get_update_model(event, bot)
    assert res is None
