from __future__ import annotations

import asyncio
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


class ChatActionLoop:
    """Контекстный менеджер для периодической отправки chat action."""

    def __init__(
        self,
        *,
        owner: ChatActionShortcutMixin,
        action: SenderAction,
        interval: float,
    ) -> None:
        if interval <= 0:
            raise ValueError("interval должен быть больше 0")

        self._owner = owner
        self._action = action
        self._interval = interval
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> ChatActionLoop:  # noqa: PYI034
        await self._owner.action(self._action)
        self._task = asyncio.create_task(self._runner())
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._stop_event.set()

        if self._task is not None:
            await self._task

    async def _wait_until_stopped(self) -> bool:
        try:
            await asyncio.wait_for(
                self._stop_event.wait(),
                timeout=self._interval,
            )
        except TimeoutError:
            return False

        return True

    async def _runner(self) -> None:
        while not self._stop_event.is_set():
            if await self._wait_until_stopped():
                return

            await self._owner.action(self._action)


class PeerShortcutMixin:
    """Общие convenience-методы для отправки сообщений в текущий peer."""

    def _ensure_bot(self) -> Bot:
        raise NotImplementedError

    def _resolve_send_target(self) -> tuple[int | None, int | None]:
        raise NotImplementedError

    async def send(
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

        return await self._ensure_bot().send_message(
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

    async def action(
        self,
        action: SenderAction = SenderAction.TYPING_ON,
    ) -> SendedAction:
        """Отправить chat action в связанный чат."""

        return await self._ensure_bot().send_action(
            chat_id=self._resolve_action_chat_id(),
            action=action,
        )

    async def mark_seen(self) -> SendedAction:
        """Отметить сообщения как прочитанные."""

        return await self.action(SenderAction.MARK_SEEN)

    def typing(
        self,
        *,
        interval: float = 4.0,
        action: SenderAction = SenderAction.TYPING_ON,
    ) -> ChatActionLoop:
        """Периодически отправлять action внутри async context manager."""

        return ChatActionLoop(
            owner=self,
            action=action,
            interval=interval,
        )
