import asyncio
from unittest.mock import AsyncMock, call, patch

import pytest
from maxapi.exceptions.max import MaxApiError
from maxapi.methods.types.getted_updates import (
    get_update_model,
    process_update_request,
    process_update_webhook,
)


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


async def test_process_update_request_logs_and_skips_unknown_updates(
    bot, caplog
):
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


async def test_get_update_model_returns_none_for_unknown_type(bot):
    """Проверяет, что get_update_model возвращает None при
    неизвестном значении update_type (новая логика).
    """
    event = {"update_type": "unknown_type"}

    res = await get_update_model(event, bot)
    assert res is None


async def test_process_update_request_skips_event_that_raised(bot, caplog):
    """Падение на одном событии не должно ронять всю пачку.

    Регрессия на issue #196: исключение из enrich_event (например,
    MaxApiError 404 от get_chat_by_id) прерывало цикл, и вся пачка
    терялась вместе с уже сдвинутым маркером.
    """
    events = {
        "updates": [
            {"update_type": "message_created", "n": 1},
            {"update_type": "message_created", "n": 2},
            {"update_type": "message_created", "n": 3},
        ]
    }

    good_first = object()
    good_last = object()

    async_mock = AsyncMock(
        side_effect=[
            good_first,
            MaxApiError(code=404, raw="chat.not.found"),
            good_last,
        ]
    )

    with patch(
        "maxapi.methods.types.getted_updates.get_update_model", async_mock
    ):
        caplog.clear()
        caplog.set_level("ERROR")

        res = await process_update_request(events, bot)

    # Битое событие пропущено, соседние обработаны
    assert res == [good_first, good_last]
    assert async_mock.call_count == 3
    assert any("пропущено" in r.message.lower() for r in caplog.records)


async def test_process_update_request_without_updates_key(bot):
    """Ответ API без ключа "updates" не должен приводить к KeyError."""
    assert await process_update_request({"marker": 42}, bot) == []


async def test_process_update_request_with_null_updates(bot):
    """updates=None трактуется как пустая пачка."""
    assert await process_update_request({"updates": None}, bot) == []


async def test_process_update_request_does_not_swallow_cancellation(bot):
    """Отмена корутины должна пролетать сквозь per-event except.

    asyncio.CancelledError с Python 3.8 наследуется напрямую от
    BaseException, поэтому `except Exception` его не перехватывает.
    Тест фиксирует инвариант: если кто-то расширит перехват до
    BaseException, остановка polling перестанет работать.
    """
    events = {"updates": [{"update_type": "message_created"}]}

    async_mock = AsyncMock(side_effect=asyncio.CancelledError)

    with (
        patch(
            "maxapi.methods.types.getted_updates.get_update_model", async_mock
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await process_update_request(events, bot)
