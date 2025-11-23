from typing import List, Optional

from pydantic import BaseModel, Field

from ...types.attachments import Attachments


from .update import Update

from ...enums.parse_mode import ParseMode

from ...types.message import NewMessageLink
from ...types.callback import Callback
from ...types.message import Message


class MessageForCallback(BaseModel):
    
    """
    Модель сообщения для ответа на callback-запрос.

    Attributes:
        text (Optional[str]): Текст сообщения.
        attachments (Optional[List[Union[AttachmentButton, Audio, Video, File, Image, Sticker, Share]]]):
            Список вложений.
        link (Optional[NewMessageLink]): Связь с другим сообщением.
        notify (Optional[bool]): Отправлять ли уведомление.
        format (Optional[ParseMode]): Режим разбора текста.
    """
    
    text: Optional[str] = None
    attachments: Optional[
        List[Attachments]
    ] = Field(default_factory=list) # type: ignore
    link: Optional[NewMessageLink] = None
    notify: Optional[bool] = True
    format: Optional[ParseMode] = None


class MessageCallback(Update):
    
    """
    Обновление с callback-событием сообщения.

    Attributes:
        message (Message): Сообщение, на которое пришёл callback.
        user_locale (Optional[str]): Локаль пользователя.
        callback (Callback): Объект callback.
    """
    
    message: Message
    user_locale: Optional[str] = None
    callback: Callback

    def get_ids(self):
        
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            tuple[Optional[int], int]: Идентификаторы чата и пользователя.
        """
        
        return (self.message.recipient.chat_id, self.callback.user.user_id)
    
    async def answer(
            self,
            notification: Optional[str] = None,
            new_text: Optional[str] = None,
            link: Optional[NewMessageLink] = None,
            notify: bool = True,
            format: Optional[ParseMode] = None,
        ):
        
        """
        Отправляет ответ на callback с возможностью изменить текст, вложения и параметры уведомления.

        Args:
            notification (str): Текст уведомления.
            new_text (Optional[str]): Новый текст сообщения.
            link (Optional[NewMessageLink]): Связь с другим сообщением.
            notify (bool): Отправлять ли уведомление.
            format (Optional[ParseMode]): Режим разбора текста.

        Returns:
            Результат вызова send_callback бота.
        """
        
        message = MessageForCallback()

        message.text = new_text
        message.attachments = self.message.body.attachments
        message.link = link
        message.notify = notify
        message.format = format
        
        return await self._ensure_bot().send_callback(
            callback_id=self.callback.callback_id,
            message=message,
            notification=notification
        )