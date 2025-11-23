from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Optional, List, Union, TYPE_CHECKING

from ..types.bot_mixin import BotMixin

from ..types.attachments import Attachments

from ..enums.text_style import TextStyle
from ..enums.parse_mode import ParseMode
from ..enums.chat_type import ChatType
from ..enums.message_link_type import MessageLinkType

from .attachments.attachment import Attachment

from .users import User


if TYPE_CHECKING:
    from ..bot import Bot
    from ..types.input_media import InputMedia, InputMediaBuffer


class MarkupElement(BaseModel):
    
    """
    Модель элемента разметки текста.

    Attributes:
        type (TextStyle): Тип разметки.
        from_ (int): Начальная позиция разметки в тексте.
        length (int): Длина разметки.
    """
    
    type: TextStyle
    from_: int = Field(..., alias='from')
    length: int

    class Config:
        populate_by_name = True


class MarkupLink(MarkupElement):
    
    """
    Модель разметки ссылки.

    Attributes:
        url (Optional[str]): URL ссылки. Может быть None.
    """
    
    url: Optional[str] = None


class Recipient(BaseModel):
    
    """
    Модель получателя сообщения.

    Attributes:
        user_id (Optional[int]): Идентификатор пользователя. Может быть None.
        chat_id (Optional[int]): Идентификатор чата. Может быть None.
        chat_type (ChatType): Тип получателя (диалог или чат).
    """
    
    user_id: Optional[int] = None
    chat_id: Optional[int] = None
    chat_type: ChatType


class MessageBody(BaseModel):
    
    """
    Модель тела сообщения.

    Attributes:
        mid (str): Уникальный идентификатор сообщения.
        seq (int): Порядковый номер сообщения.
        text (str): Текст сообщения. Может быть None.
        attachments (Optional[List[Union[AttachmentButton, Audio, Video, File, Image, Sticker, Share]]]): 
            Список вложений. По умолчанию пустой.
        markup (Optional[List[Union[MarkupLink, MarkupElement]]]): Список элементов разметки. По умолчанию пустой.
    """
    
    mid: str
    seq: int
    text: Optional[str] = None
    attachments: Optional[
        List[Attachments]
    ] = Field(default_factory=list) # type: ignore

    markup: Optional[
        List[
            Union[
                MarkupLink, MarkupElement
            ]
        ]
    ] = Field(default_factory=list) # type: ignore


class MessageStat(BaseModel):
    
    """
    Модель статистики сообщения.

    Attributes:
        views (int): Количество просмотров сообщения.
    """
    
    views: int


class LinkedMessage(BaseModel):
    
    """
    Модель связанного сообщения.

    Attributes:
        type (MessageLinkType): Тип связи.
        sender (Optional[User]): Отправитель связанного сообщения, может быть None, если связанное сообщение отправлено каналом https://github.com/love-apples/maxapi/issues/11.
        chat_id (Optional[int]): Идентификатор чата. Может быть None.
        message (MessageBody): Тело связанного сообщения.
    """
    
    type: MessageLinkType
    sender: Optional[User] = None
    chat_id: Optional[int] = None
    message: MessageBody


class Message(BaseModel, BotMixin):
    
    """
    Модель сообщения.

    Attributes:
        sender (User): Отправитель сообщения.
        recipient (Recipient): Получатель сообщения.
        timestamp (int): Временная метка сообщения.
        link (Optional[LinkedMessage]): Связанное сообщение. Может быть None.
        body (Optional[MessageBody]): Тело сообщения. Может быть None.
        stat (Optional[MessageStat]): Статистика сообщения. Может быть None.
        url (Optional[str]): URL сообщения. Может быть None.
        bot (Optional[Bot]): Объект бота, исключается из сериализации.
    """
    
    sender: User
    recipient: Recipient
    timestamp: int
    link: Optional[LinkedMessage] = None
    body: MessageBody
    stat: Optional[MessageStat] = None
    url: Optional[str] = None
    bot: Optional[Any] = Field(default=None, exclude=True) # pyright: ignore[reportRedeclaration]
    
    if TYPE_CHECKING:
        bot: Optional[Bot] # type: ignore

    async def answer(
            self,
            text: Optional[str] = None,
            attachments: Optional[List[Attachment | InputMedia | InputMediaBuffer]] = None,
            link: Optional[NewMessageLink] = None,
            notify: Optional[bool] = None,
            parse_mode: Optional[ParseMode] = None
        ):
        
        """
        Отправляет сообщение (автозаполнение chat_id, user_id).

        Args:
            text (str, optional): Текст ответа. Может быть None.
            attachments (List[Attachment | InputMedia | InputMediaBuffer], optional): Список вложений. Может быть None.
            link (NewMessageLink, optional): Связь с другим сообщением. Может быть None.
            notify (bool): Флаг отправки уведомления. По умолчанию True.
            parse_mode (ParseMode, optional): Режим форматирования текста. Может быть None.

        Returns:
            Any: Результат выполнения метода send_message бота.
        """
        
        return await self._ensure_bot().send_message(
            chat_id=self.recipient.chat_id,
            user_id=self.recipient.user_id,
            text=text,
            attachments=attachments,
            link=link,
            notify=notify,
            parse_mode=parse_mode
        )
        
    async def reply(
            self,
            text: Optional[str] = None,
            attachments: Optional[List[Attachment | InputMedia | InputMediaBuffer]] = None,
            notify: Optional[bool] = None,
            parse_mode: Optional[ParseMode] = None
        ):
        
        """
        Отправляет ответное сообщение (автозаполнение chat_id, user_id, link).

        Args:
            text (str, optional): Текст ответа. Может быть None.
            attachments (List[Attachment | InputMedia | InputMediaBuffer], optional): Список вложений. Может быть None.
            notify (bool): Флаг отправки уведомления. По умолчанию True.
            parse_mode (ParseMode, optional): Режим форматирования текста. Может быть None.

        Returns:
            Any: Результат выполнения метода send_message бота.
        """
        
        return await self._ensure_bot().send_message(
            chat_id=self.recipient.chat_id,
            user_id=self.recipient.user_id,
            text=text,
            attachments=attachments,
            link=NewMessageLink(
                type=MessageLinkType.REPLY,
                mid=self.body.mid
            ),
            notify=notify,
            parse_mode=parse_mode
        )
        
    async def forward(
            self,
            chat_id, 
            user_id: Optional[int] = None,
            attachments: Optional[List[Attachment | InputMedia | InputMediaBuffer]] = None,
            notify: Optional[bool] = None,
            parse_mode: Optional[ParseMode] = None
        ):
        
        """
        Пересылает отправленное сообщение в указанный чат (автозаполнение link).

        Args:
            chat_id (int): ID чата для отправки (обязателен, если не указан user_id)
            user_id (int): ID пользователя для отправки (обязателен, если не указан chat_id). По умолчанию None
            attachments (List[Attachment | InputMedia | InputMediaBuffer], optional): Список вложений. Может быть None.
            notify (bool): Флаг отправки уведомления. По умолчанию True.
            parse_mode (ParseMode, optional): Режим форматирования текста. Может быть None.

        Returns:
            Any: Результат выполнения метода send_message бота.
        """
        
        return await self._ensure_bot().send_message(
            chat_id=chat_id,
            user_id=user_id,
            attachments=attachments,
            link=NewMessageLink(
                type=MessageLinkType.FORWARD,
                mid=self.body.mid
            ),
            notify=notify,
            parse_mode=parse_mode
        )
    
    async def edit(
            self,
            text: Optional[str] = None,
            attachments: Optional[List[Attachment | InputMedia | InputMediaBuffer] | List[Attachments]] = None,
            link: Optional[NewMessageLink] = None,
            notify: bool = True,
            parse_mode: Optional[ParseMode] = None
        ):
        
        """
        Редактирует текущее сообщение.

        Args:
            text (str, optional): Новый текст сообщения. Может быть None.
            attachments (List[Attachment | InputMedia | InputMediaBuffer], optional): Новые вложения. Может быть None.
            link (NewMessageLink, optional): Новая связь с сообщением. Может быть None.
            notify (bool): Флаг отправки уведомления. По умолчанию True.
            parse_mode (ParseMode, optional): Режим форматирования текста. Может быть None.

        Returns:
            Any: Результат выполнения метода edit_message бота.
        """
        
        if link is None and self.link:
            link = NewMessageLink(type=self.link.type, mid=self.link.message.mid)
            
        if attachments is None and self.body.attachments:
            attachments = self.body.attachments
            
        return await self._ensure_bot().edit_message(
            message_id=self.body.mid,
            text=text,
            attachments=attachments,
            link=link,
            notify=notify,
            parse_mode=parse_mode
        )
    
    async def delete(self):
        
        """
        Удаляет текущее сообщение.

        Returns:
            Any: Результат выполнения метода delete_message бота.
        """
        
        return await self._ensure_bot().delete_message(
            message_id=self.body.mid,
        )
    
    async def pin(self, notify: bool = True):
        
        """
        Закрепляет текущее сообщение в чате.

        Args:
            notify (bool): Флаг отправки уведомления. По умолчанию True.

        Returns:
            Any: Результат выполнения метода pin_message бота.
        """
        
        if self.recipient.chat_id is None:
            raise ValueError('chat_id не может быть None')
        
        return await self._ensure_bot().pin_message(
            chat_id=self.recipient.chat_id,
            message_id=self.body.mid,
            notify=notify
        )


class Messages(BaseModel):
    
    """
    Модель списка сообщений.

    Attributes:
        messages (List[Message]): Список сообщений.
        bot (Optional[Bot]): Объект бота, исключается из сериализации.
    """
    
    messages: List[Message]
    bot: Optional[Any] = Field(default=None, exclude=True)  # pyright: ignore[reportRedeclaration]
    
    if TYPE_CHECKING:
        bot: Optional[Bot] # type: ignore


class NewMessageLink(BaseModel):
    
    """
    Модель ссылки на новое сообщение.

    Attributes:
        type (MessageLinkType): Тип связи.
        mid (str): Идентификатор сообщения.
    """
    
    type: MessageLinkType
    mid: str