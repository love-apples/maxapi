import json
from typing import TYPE_CHECKING, Any

from ...enums.update import UpdateType
from ...loggers import logger_dp
from ...types.updates import (
    MALFORMED_UPDATE_DISCLAIMER,
    UNKNOWN_UPDATE_DISCLAIMER,
    UNSUPPORTED_MESSAGE_UPDATE_DISCLAIMER,
    UpdateUnion,
    UpdateUnionAdapter,
)
from ...utils.updates import enrich_event

if TYPE_CHECKING:
    from ...bot import Bot

_SERVICE_UPDATE_TYPES = frozenset(
    {
        UpdateType.ON_STARTED,
        UpdateType.RAW_API_RESPONSE,
    }
)
_KNOWN_UPDATE_TYPES = frozenset(UpdateType) - _SERVICE_UPDATE_TYPES


def _dump_event_json(event: dict[str, Any]) -> str:
    """Сериализовать событие в однострочный JSON для лога.

    Несериализуемые объекты (enum, datetime и т.п.) заменяются
    строковым представлением.

    Returns:
        JSON-строка события или её строковое представление,
        если событие не сериализуется.
    """

    try:
        return json.dumps(event, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(event)


def warn_unprocessable_event(event: dict[str, Any]) -> None:
    """Предупредить в лог о событии, которое не удалось разобрать.

    Различает три случая: известную проблему на стороне MAX
    (message_created без тела сообщения — например, голосовое
    сообщение боту), известный тип события с некорректным
    содержимым и неизвестный тип события. В лог всегда попадает
    payload события, а в сообщении указано, куда обращаться.

    Args:
        event: Словарь события из ответа API или вебхука.
    """

    update_type = event.get("update_type")
    event_json = _dump_event_json(event)

    if update_type == UpdateType.MESSAGE_CREATED and "message" not in event:
        logger_dp.warning(
            UNSUPPORTED_MESSAGE_UPDATE_DISCLAIMER.format(
                event_json=event_json,
            )
        )
    elif update_type in _KNOWN_UPDATE_TYPES:
        logger_dp.warning(
            MALFORMED_UPDATE_DISCLAIMER.format(
                update_type=update_type,
                event_json=event_json,
            )
        )
    else:
        logger_dp.warning(
            UNKNOWN_UPDATE_DISCLAIMER.format(
                update_type=update_type,
                event_json=event_json,
            )
        )


async def get_update_model(
    event: dict[str, Any], bot: "Bot"
) -> UpdateUnion | None:
    """Конвертировать словарь с событием в модель обновления.

    При любой ошибке валидации (неизвестный тип события или
    известный тип с некорректным содержимым) возвращает ``None``,
    чтобы не ломать процесс получения обновлений. Классификацию
    причины и предупреждение в лог выполняет вызывающий код через
    :func:`warn_unprocessable_event`.

    Args:
        event: Словарь события из ответа API или вебхука.
        bot: Экземпляр бота.

    Returns:
        Модель события или ``None``, если событие не распознано.
    """

    try:
        event_object = UpdateUnionAdapter.validate_python(event)
    except ValueError:
        # Пришло новое событие, которое данная библиотека пока
        # не умеет обрабатывать. Возвращаем None, чтобы обработать это
        # в вызывающем коде и не ломать процесс получения обновлений
        return None

    return await enrich_event(event_object=event_object, bot=bot)


async def process_update_request(
    events: dict[str, Any],
    bot: "Bot",
) -> list[UpdateUnion]:
    """Конвертировать словарь с обновлениями в список моделей.

    Нераспознанные события пропускаются с предупреждением в лог.

    Args:
        events: Ответ API метода GET /updates.
        bot: Экземпляр бота.

    Returns:
        Список разобранных событий.
    """

    events_models = []

    for event in events["updates"]:
        event_model = await get_update_model(event, bot)
        if event_model is None:
            warn_unprocessable_event(event)
            continue

        events_models.append(event_model)

    return events_models


async def process_update_webhook(
    event_json: dict[str, Any], bot: "Bot"
) -> UpdateUnion | None:
    """Конвертировать JSON события вебхука в модель обновления.

    Args:
        event_json: Тело вебхук-запроса.
        bot: Экземпляр бота.

    Returns:
        Модель события или ``None``, если событие не распознано.
    """

    return await get_update_model(bot=bot, event=event_json)
