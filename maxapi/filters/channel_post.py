from __future__ import annotations

from ..enums.chat_type import ChatType
from ..filters.filter import BaseFilter
from ..types.updates.message_created import MessageCreated
from ..types.updates.message_edited import MessageEdited


class ChannelPostFilter(BaseFilter):
    """Фильтр событий сообщений из канала."""

    async def __call__(self, event) -> bool:
        if not isinstance(event, (MessageCreated, MessageEdited)):
            return False

        return event.message.recipient.chat_type == ChatType.CHANNEL


