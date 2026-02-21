__all__ = ["Message", "MessageCallback", "MessageForCallback"]

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from ...enums.parse_mode import ParseMode
from ...enums.update import UpdateType
from ...types.attachments import Attachments
from ...types.callback import Callback
from ...types.message import Message, NewMessageLink
from .base_update import BaseUpdate

if TYPE_CHECKING:
    from ...methods.types.sended_callback import SendedCallback


class MessageForCallback(BaseModel):
    """
    Модель сообщения для ответа на callback-запрос.

    Attributes:
        text (Optional[str]): Текст сообщения.
        attachments (Optional[List[Union[AttachmentButton, Audio, Video,
            File, Image, Sticker, Share]]]):
            Список вложений.
        link (Optional[NewMessageLink]): Связь с другим сообщением.
        notify (Optional[bool]): Отправлять ли уведомление.
        format (Optional[ParseMode]): Режим разбора текста.
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
        message (Optional[Message]): Изначальное сообщение, содержащее
            встроенную клавиатуру. Может быть null, если оно было
            удалено к моменту, когда бот получил это обновление.
        user_locale (Optional[str]): Локаль пользователя.
        callback (Callback): Объект callback.
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

    async def answer(
        self,
        notification: str | None = None,
        new_text: str | None = None,
        link: NewMessageLink | None = None,
        format: ParseMode | None = None,
        *,
        notify: bool = True,
        raise_if_not_exists: bool = True,
    ) -> "SendedCallback":
        """
        Отправляет ответ на callback с возможностью изменить текст,
        вложения и параметры уведомления.

        Args:
            notification (str): Текст уведомления.
            new_text (Optional[str]): Новый текст сообщения.
            link (Optional[NewMessageLink]): Связь с другим сообщением.
            notify (bool): Отправлять ли уведомление.
            format (Optional[ParseMode]): Режим разбора текста.
            raise_if_not_exists: Выдавать ошибку при отсутствии сообщения,
                если пытаются изменить его содержимое (new_text/link/format).

        Returns:
            SendedCallback: Результат вызова send_callback бота.
        """

        # Если исходного сообщения нет (например, оно удалено),
        # не стоит синтезировать пустой payload message.
        # Два варианта поведения:
        #  - если вызывающий просит изменить сообщение (new_text/link/format)
        #    => выбросить исключение
        #  - иначе отправить только notification с message=None,
        #  чтобы API не получил пустой объект message
        original_body = None
        if self.message is not None:
            original_body = self.message.body

        if original_body is None:
            # если пытаются изменить контент/вложение/связь
            if raise_if_not_exists and (
                new_text is not None or link is not None or format is not None
            ):
                raise ValueError(
                    "Невозможно изменить сообщение: "
                    "исходное сообщение отсутствует"
                )

            # отправляем только уведомление (без поля message)
            return await self._ensure_bot().send_callback(
                callback_id=self.callback.callback_id,
                message=None,
                notification=notification,
            )

        # Если исходное сообщение есть —
        # собираем MessageForCallback на его основе
        message_for_callback = MessageForCallback()
        message_for_callback.text = new_text

        attachments: list[Attachments] = original_body.attachments or []

        message_for_callback.attachments = attachments
        message_for_callback.link = link
        message_for_callback.notify = notify
        message_for_callback.format = format

        return await self._ensure_bot().send_callback(
            callback_id=self.callback.callback_id,
            message=message_for_callback,
            notification=notification,
        )
