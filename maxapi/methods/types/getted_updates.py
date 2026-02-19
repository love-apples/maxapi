import logging
from typing import TYPE_CHECKING, Any

from ...types.updates import (
    UNKNOWN_UPDATE_DISCLAIMER,
    UpdateUnion,
    UpdateUnionAdapter,
)
from ...utils.updates import enrich_event

if TYPE_CHECKING:
    from ...bot import Bot

logger = logging.getLogger(__name__)


async def get_update_model(event: dict, bot: "Bot") -> UpdateUnion | None:
    """Конвертировать словарь с событием в модель обновления."""
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
    """Конвертировать словарь с обновлениями в список моделей."""
    events_models = []

    for event in events["updates"]:
        event_model = await get_update_model(event, bot)
        if event_model is None:
            update_type = event["update_type"]
            logger.warning(
                UNKNOWN_UPDATE_DISCLAIMER.format(update_type=update_type)
            )
            continue

        events_models.append(event_model)

    return events_models


async def process_update_webhook(
    event_json: dict[str, Any], bot: "Bot"
) -> UpdateUnion | None:
    return await get_update_model(bot=bot, event=event_json)
