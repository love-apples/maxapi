from __future__ import annotations

from typing import TYPE_CHECKING

from ..enums.sender_action import SenderAction

if TYPE_CHECKING:
    from ..bot import Bot
    from ..enums.parse_mode import ParseMode, TextFormat
    from ..methods.types.sended_action import SendedAction
    from ..methods.types.sended_message import SendedMessage
    from .attachments.attachment import Attachment
    from .attachments.upload import AttachmentUpload
    from .input_media import InputMedia, InputMediaBuffer
    from .message import NewMessageLink


class PeerShortcutMixin:
    """Общие convenience-методы для отправки сообщений в текущий peer."""

    def _ensure_bot(self) -> Bot:
        raise NotImplementedError

    def _resolve_send_target(self) -> tuple[int | None, int | None]:
        raise NotImplementedError

    def send(
        self,
        text: str | None = None,
        attachments: list[
            Attachment | InputMedia | InputMediaBuffer | AttachmentUpload
        ]
        | None = None,
        link: NewMessageLink | None = None,
        format: TextFormat | None = None,
        parse_mode: ParseMode | None = None,
        *,
        notify: bool | None = None,
        disable_link_preview: bool | None = None,
        sleep_after_input_media: bool | None = True,
    ) -> SendedMessage | None:
        """Отправить новое сообщение в текущий peer-контекст."""

        chat_id, user_id = self._resolve_send_target()

        return self._ensure_bot().send_message(
            chat_id=chat_id,
            user_id=user_id,
            text=text,
            attachments=attachments,
            link=link,
            notify=notify,
            format=format,
            parse_mode=parse_mode,
            disable_link_preview=disable_link_preview,
            sleep_after_input_media=sleep_after_input_media,
        )


class ChatActionShortcutMixin:
    """Convenience-методы для отправки chat actions."""

    def _ensure_bot(self) -> Bot:
        raise NotImplementedError

    def _resolve_action_chat_id(self) -> int:
        raise NotImplementedError

    def action(
        self,
        action: SenderAction = SenderAction.TYPING_ON,
    ) -> SendedAction:
        """Отправить chat action в связанный чат."""

        return self._ensure_bot().send_action(
            chat_id=self._resolve_action_chat_id(),
            action=action,
        )

    def mark_seen(self) -> SendedAction:
        """Отметить сообщения как прочитанные."""

        return self.action(SenderAction.MARK_SEEN)
