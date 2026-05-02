from __future__ import annotations

__all__ = ["Message", "MessageCallback", "MessageForCallback"]

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from ...enums.parse_mode import ParseMode
from ...enums.update import UpdateType
from ...types.attachments import Attachments
from ...types.callback import Callback  # noqa: TC001
from ...types.message import Message, NewMessageLink
from .base_update import BaseUpdate

if TYPE_CHECKING:
    from ...enums.parse_mode import TextFormat
    from ...methods.types.deleted_message import DeletedMessage
    from ...methods.types.deleted_pin_message import DeletedPinMessage
    from ...methods.types.pinned_message import PinnedMessage
    from ...methods.types.sended_callback import SendedCallback
    from ...methods.types.sended_message import SendedMessage
    from ...types.attachments.attachment import Attachment
    from ...types.attachments.upload import AttachmentUpload
    from ...types.input_media import InputMedia, InputMediaBuffer


class MessageForCallback(BaseModel):
    """
    Модель сообщения для ответа на callback-запрос.

    Attributes:
        text: Текст сообщения.
        attachments: Список вложений. По умолчанию пустой список.
        link: Связь с другим сообщением.
        notify: Отправлять ли уведомление.
        format: Режим разбора текста.
    """

    text: str | None = None
    attachments: list[Attachments] | None = Field(default_factory=list)  # type: ignore
    link: NewMessageLink | None = None
    notify: bool | None = True
    format: ParseMode | None = None


class MessageCallback(BaseUpdate):
    """
    Обновление с callback-событием сообщения.

    Attributes:
        message: Изначальное сообщение, содержащее
            встроенную клавиатуру. Может быть None, если оно было
            удалено к моменту, когда бот получил это обновление.
        user_locale: Локаль пользователя.
        callback: Объект callback.
    """

    message: Message | None = None
    user_locale: str | None = None
    callback: Callback
    update_type: Literal[UpdateType.MESSAGE_CALLBACK] = (
        UpdateType.MESSAGE_CALLBACK
    )

    def get_ids(self) -> tuple[int | None, int]:
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            tuple[Optional[int], int]: Идентификаторы чата и пользователя.
        """

        chat_id: int | None = None
        if self.message is not None:
            chat_id = self.message.recipient.chat_id

        return chat_id, self.callback.user.user_id

    def _require_message(self) -> Message:
        if self.message is None:
            raise ValueError(
                "Невозможно выполнить операцию: исходное сообщение отсутствует"
            )

        if self.message.bot is None and self.bot is not None:
            self.message.bot = self.bot

        return self.message

    async def ack(
        self,
        notification: str | None = None,
    ) -> SendedCallback:
        """Подтвердить callback без изменения исходного сообщения."""

        return await self._ensure_bot().send_callback(
            callback_id=self.callback.callback_id,
            message=None,
            notification=notification,
        )

    async def defer(
        self,
        notification: str | None = None,
    ) -> SendedCallback:
        """Семантический alias для ack()."""

        return await self.ack(notification=notification)

    async def edit(
        self,
        text: str | None = None,
        link: NewMessageLink | None = None,
        format: ParseMode | None = None,
        *,
        notification: str | None = None,
        notify: bool = True,
        raise_if_not_exists: bool = True,
    ) -> SendedCallback:
        """Изменить сообщение, связанное с callback."""

        message = self.message
        original_body = None if message is None else message.body

        if original_body is None:
            if raise_if_not_exists and (
                text is not None or link is not None or format is not None
            ):
                raise ValueError(
                    "Невозможно изменить сообщение: "
                    "исходное сообщение отсутствует"
                )

            return await self.ack(notification=notification)

        bot = self._ensure_bot()
        message_for_callback = MessageForCallback(
            text=text,
            attachments=original_body.attachments or [],
            link=link,
            notify=notify,
            format=bot.resolve_format(format),
        )

        return await bot.send_callback(
            callback_id=self.callback.callback_id,
            message=message_for_callback,
            notification=notification,
        )

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
        """Отправить новое сообщение в тот же peer, откуда пришел callback."""

        return await self._require_message().send(
            text=text,
            attachments=attachments,
            link=link,
            format=format,
            parse_mode=parse_mode,
            notify=notify,
            disable_link_preview=disable_link_preview,
            sleep_after_input_media=sleep_after_input_media,
        )

    async def reply(
        self,
        text: str | None = None,
        attachments: list[
            Attachment | InputMedia | InputMediaBuffer | AttachmentUpload
        ]
        | None = None,
        format: TextFormat | None = None,
        parse_mode: ParseMode | None = None,
        *,
        notify: bool | None = None,
        disable_link_preview: bool | None = None,
        sleep_after_input_media: bool | None = True,
    ) -> SendedMessage | None:
        """Отправить reply на исходное сообщение callback."""

        return await self._require_message().reply(
            text=text,
            attachments=attachments,
            format=format,
            parse_mode=parse_mode,
            notify=notify,
            disable_link_preview=disable_link_preview,
            sleep_after_input_media=sleep_after_input_media,
        )

    async def delete(self) -> DeletedMessage:
        """Удалить исходное сообщение callback."""

        return await self._require_message().delete()

    async def pin(self, *, notify: bool = True) -> PinnedMessage:
        """Закрепить исходное сообщение callback."""

        return await self._require_message().pin(notify=notify)

    async def unpin(self) -> DeletedPinMessage:
        """Снять закрепление сообщения callback."""

        return await self._require_message().unpin()

    async def answer(
        self,
        notification: str | None = None,
        new_text: str | None = None,
        link: NewMessageLink | None = None,
        format: ParseMode | None = None,
        *,
        notify: bool = True,
        raise_if_not_exists: bool = True,
    ) -> SendedCallback:
        """
        Отправляет ответ на callback с возможностью изменить текст
        и параметры уведомления.

        Args:
            notification: Текст уведомления.
            new_text: Новый текст сообщения.
            link: Связь с другим сообщением.
            notify: Отправлять ли уведомление.
            format: Режим разбора текста.
            raise_if_not_exists: Выдавать ошибку при отсутствии сообщения,
                если пытаются изменить его содержимое (new_text/link/format).

        Returns:
            SendedCallback: Результат вызова send_callback бота.
        """
        return await self.edit(
            text=new_text,
            link=link,
            format=format,
            notification=notification,
            notify=notify,
            raise_if_not_exists=raise_if_not_exists,
        )
