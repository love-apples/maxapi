from __future__ import annotations

from typing import TYPE_CHECKING

from ..enums.attachment import AttachmentType
from ..filters.filter import BaseFilter
from ..types.attachments.contact import Contact as ContactAttachment
from ..types.updates.message_created import MessageCreated
from ..types.updates.message_edited import MessageEdited

if TYPE_CHECKING:
    from ..types.updates import UpdateUnion


class Contact(BaseFilter):
    """Фильтр событий сообщений с вложением-контактом."""

    async def __call__(
        self, event: UpdateUnion
    ) -> bool | dict[str, ContactAttachment]:
        if not isinstance(event, (MessageCreated, MessageEdited)):
            return False

        body = event.message.body
        if body is None or not body.attachments:
            return False

        for att in body.attachments:
            if getattr(att, "type", None) == AttachmentType.CONTACT:
                if isinstance(att, ContactAttachment):
                    return {"contact": att}

                return {"contact": ContactAttachment.model_validate(att)}

        return False


ContactFilter = Contact
