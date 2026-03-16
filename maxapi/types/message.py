from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..enums.chat_type import ChatType
from ..enums.message_link_type import MessageLinkType
from ..enums.text_style import TextStyle
from ..types.attachments import Attachments
from ..types.bot_mixin import BotMixin
from ..utils.formatting import (
    Bold,
    Code,
    Heading,
    Italic,
    Link,
    Strikethrough,
    Text,
    Underline,
    UserMention,
)
from .users import User

if TYPE_CHECKING:
    from ..bot import Bot
    from ..enums.parse_mode import ParseMode
    from ..methods.types.deleted_message import DeletedMessage
    from ..methods.types.edited_message import EditedMessage
    from ..methods.types.pinned_message import PinnedMessage
    from ..methods.types.sended_message import SendedMessage
    from ..types.attachments.upload import AttachmentUpload
    from ..types.input_media import InputMedia, InputMediaBuffer
    from .attachments.attachment import Attachment


class MarkupElement(BaseModel):
    """
    Модель элемента разметки текста.

    Attributes:
        type (TextStyle): Тип разметки.
        from_ (int): Начальная позиция разметки в тексте.
        length (int): Длина разметки.
    """

    type: TextStyle
    from_: int = Field(..., alias="from")
    length: int

    model_config = ConfigDict(
        populate_by_name=True,
    )


class MarkupLink(MarkupElement):
    """
    Модель разметки ссылки.

    Attributes:
        url (Optional[str]): URL ссылки. Может быть None.
    """

    type: Literal[TextStyle.LINK] = TextStyle.LINK
    url: str | None = None


class MarkupUserMention(MarkupElement):
    """
    Модель разметки упоминания пользователя.

    Attributes:
        user_id (Optional[int]): Идентификатор пользователя. Может быть None.
        user_link (Optional[str]): Ссылка на пользователя. Может быть None.
    """

    type: Literal[TextStyle.USER_MENTION] = TextStyle.USER_MENTION
    user_id: int | None = None
    user_link: str | None = None


class Recipient(BaseModel):
    """
    Модель получателя сообщения.

    Attributes:
        user_id (Optional[int]): Идентификатор пользователя. Может быть None.
        chat_id (Optional[int]): Идентификатор чата. Может быть None.
        chat_type (ChatType): Тип получателя (диалог или чат).
    """

    user_id: int | None = None
    chat_id: int | None = None
    chat_type: ChatType


class MessageBody(BaseModel):
    """
    Модель тела сообщения.

    Attributes:
        mid (str): Уникальный идентификатор сообщения.
        seq (int): Порядковый номер сообщения.
        text (str): Текст сообщения. Может быть None.
        attachments (Optional[List[Union[AttachmentButton, Audio, Video,
            File, Image, Sticker, Share]]]):
            Список вложений. По умолчанию пустой.
        markup (Optional[List[Union[MarkupLink, MarkupUserMention,
            MarkupElement]]]): Список элементов разметки. По умолчанию пустой.
    """

    mid: str
    seq: int
    text: str | None = None
    attachments: list[Attachments] | None = Field(default_factory=list)  # type: ignore

    markup: list[MarkupUserMention | MarkupLink | MarkupElement] | None = (
        Field(default_factory=list)
    )  # type: ignore

    @property
    def html_text(self) -> str | None:
        """
        Преобразует исходный текст сообщения в HTML строку,
        основываясь на разметке markup с помощью класса Text.
        """
        if self.text is None:
            return None

        decorated = self.text_decorated
        if decorated:
            return decorated.as_html()
        return None

    @property
    def md_text(self) -> str | None:
        """
        Преобразует исходный текст сообщения в Markdown строку,
        основываясь на разметке markup с помощью класса Text.
        """
        if self.text is None:
            return None

        decorated = self.text_decorated
        if decorated:
            return decorated.as_markdown()
        return None

    @property
    def text_decorated(self) -> Text | None:  # noqa: C901
        """
        Разбирает текст и разметку сообщения в дерево форматирования.
        Если текст отсутствует, возвращает ``None``.
        Если разметка отсутствует, возвращает ``Text`` с простым текстом.

        Returns:
            Optional[Text]: Дерево форматирования или None.
        """
        if self.text is None:
            return None

        text = self.text
        markup = self.markup or []

        if not markup:
            return Text(text)

        order = {
            TextStyle.STRONG: 1,
            TextStyle.EMPHASIZED: 2,
            TextStyle.UNDERLINE: 3,
            TextStyle.STRIKETHROUGH: 4,
            TextStyle.MONOSPACED: 5,
            TextStyle.HEADING: 6,
            TextStyle.LINK: 7,
            TextStyle.USER_MENTION: 8,
        }

        char_styles: list[
            list[tuple[TextStyle, str | None | tuple[str, int]]]
        ] = []
        for i in range(len(text)):
            active = []
            for m in markup:
                if m.from_ <= i < m.from_ + m.length:
                    if m.type == TextStyle.LINK:
                        val = getattr(m, "url", None)
                    elif m.type == TextStyle.USER_MENTION:
                        display_text = text[m.from_ : m.from_ + m.length]
                        uid = getattr(m, "user_id", None) or 0
                        val = (display_text, uid)
                    else:
                        val = None
                    active.append((m.type, val))

            active.sort(key=lambda x: order.get(x[0], 99))
            unique_active = []
            for a in active:
                if a not in unique_active:
                    unique_active.append(a)
            char_styles.append(unique_active)

        parts: list = []
        current_chunk = ""
        current_tags = char_styles[0] if char_styles else []

        style_to_node: dict[Any, Any] = {
            TextStyle.STRONG: Bold,
            TextStyle.EMPHASIZED: Italic,
            TextStyle.UNDERLINE: Underline,
            TextStyle.STRIKETHROUGH: Strikethrough,
            TextStyle.MONOSPACED: Code,
            TextStyle.HEADING: Heading,
        }

        def wrap_chunk(
            chunk: str,
            tags: list[tuple[TextStyle, str | None | tuple[str, int]]],
        ) -> object:
            node: object = chunk
            for style, val in reversed(tags):
                if style == TextStyle.LINK:
                    node = Link(node, url=val or "")  # type: ignore[arg-type]
                elif style == TextStyle.USER_MENTION:
                    display_text, uid = (
                        val if isinstance(val, tuple) else (chunk, 0)
                    )
                    node = UserMention(display_text, user_id=uid)
                elif style in style_to_node:
                    node = style_to_node[style](node)
            return node

        for i, tags in enumerate(char_styles):
            if tags == current_tags:
                current_chunk += text[i]
            else:
                parts.append(wrap_chunk(current_chunk, current_tags))
                current_chunk = text[i]
                current_tags = tags

        if current_chunk:
            parts.append(wrap_chunk(current_chunk, current_tags))

        return Text(*parts)


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
        sender (Optional[User]): Отправитель связанного сообщения,
            может быть None, если связанное сообщение отправлено каналом
            https://github.com/love-apples/maxapi/issues/11.
        chat_id (Optional[int]): Идентификатор чата. Может быть None.
        message (MessageBody): Тело связанного сообщения.
    """

    type: MessageLinkType
    sender: User | None = None
    chat_id: int | None = None
    message: MessageBody


class Message(BaseModel, BotMixin):
    """
    Модель сообщения.

    Attributes:
        sender (Optional[User]): Отправитель сообщения, может быть None,
            если сообщение отправлено каналом
            https://github.com/love-apples/maxapi/discussions/14.
        recipient (Recipient): Получатель сообщения.
        timestamp (int): Временная метка сообщения.
        link (Optional[LinkedMessage]): Связанное сообщение. Может быть None.
        body (Optional[MessageBody]): Содержимое сообщения.
            Текст + вложения. Может быть null, если сообщение содержит
            только пересланное сообщение
        stat (Optional[MessageStat]): Статистика сообщения. Может быть None.
        url (Optional[str]): URL сообщения. Может быть None.
        bot (Optional[Bot]): Объект бота, исключается из сериализации.
    """

    sender: User | None = None
    recipient: Recipient
    timestamp: int
    link: LinkedMessage | None = None
    body: MessageBody | None = None
    stat: MessageStat | None = None
    url: str | None = None
    bot: Any | None = Field(  # pyright: ignore[reportRedeclaration]
        default=None, exclude=True
    )

    if TYPE_CHECKING:
        bot: Bot | None  # type: ignore

    async def answer(
        self,
        text: str | None = None,
        attachments: list[
            Attachment | InputMedia | InputMediaBuffer | AttachmentUpload
        ]
        | None = None,
        link: NewMessageLink | None = None,
        parse_mode: ParseMode | None = None,
        *,
        notify: bool | None = None,
        disable_link_preview: bool | None = None,
        sleep_after_input_media: bool | None = True,
    ) -> SendedMessage | None:
        """
        Отправляет сообщение (автозаполнение chat_id, user_id).

        Args:
            text (str, optional): Текст ответа. Может быть None.
            attachments (List[Attachment | InputMedia | InputMediaBuffer
                | AttachmentUpload], optional): Список вложений.
                Может быть None.
            link (NewMessageLink, optional): Связь с другим сообщением.
                Может быть None.
            parse_mode (ParseMode, optional): Режим форматирования текста.
                Может быть None.
            notify (bool): Флаг отправки уведомления. По умолчанию True.
            disable_link_preview (bool, optional): Флаг генерации превью.
            sleep_after_input_media (bool, optional): Флаг задержки
                после отправки вложений типа InputMedia. По умолчанию True.

        Returns:
            Optional[SendedMessage]: Результат выполнения метода
                send_message бота.
        """

        return await self._ensure_bot().send_message(
            chat_id=self.recipient.chat_id,
            user_id=self.recipient.user_id,
            text=text,
            attachments=attachments,
            link=link,
            notify=notify,
            parse_mode=parse_mode,
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
        parse_mode: ParseMode | None = None,
        *,
        notify: bool | None = None,
        disable_link_preview: bool | None = None,
        sleep_after_input_media: bool | None = True,
    ) -> SendedMessage | None:
        """
        Отправляет ответное сообщение (автозаполнение chat_id, user_id, link).

        Args:
            text (str, optional): Текст ответа. Может быть None.
            attachments (List[Attachment | InputMedia | InputMediaBuffer
                | AttachmentUpload], optional): Список вложений.
                Может быть None.
            notify (bool): Флаг отправки уведомления. По умолчанию True.
            parse_mode (ParseMode, optional): Режим форматирования текста.
                Может быть None.
            disable_link_preview (bool, optional): Флаг генерации превью.
            sleep_after_input_media: Optional[bool] = True,

        Returns:
            Optional[SendedMessage]: Результат выполнения метода
                send_message бота.
        """

        if self.body is None:
            msg = "Невозможно ответить: поле body отсутствует у сообщения"
            raise ValueError(msg)

        if self.recipient.chat_id is None:
            msg = "Невозможно ответить: chat_id отсутствует"
            raise ValueError(msg)

        return await self._ensure_bot().send_message(
            chat_id=self.recipient.chat_id,
            user_id=self.recipient.user_id,
            text=text,
            attachments=attachments,
            link=NewMessageLink(type=MessageLinkType.REPLY, mid=self.body.mid),
            notify=notify,
            parse_mode=parse_mode,
            disable_link_preview=disable_link_preview,
            sleep_after_input_media=sleep_after_input_media,
        )

    async def forward(
        self,
        chat_id: int | None,
        user_id: int | None = None,
        attachments: list[
            Attachment | InputMedia | InputMediaBuffer | AttachmentUpload
        ]
        | None = None,
        parse_mode: ParseMode | None = None,
        *,
        notify: bool | None = None,
        disable_link_preview: bool | None = None,
        sleep_after_input_media: bool | None = True,
    ) -> SendedMessage | None:
        """
        Пересылает отправленное сообщение в указанный чат.
        (автозаполнение link)

        Args:
            chat_id (int): ID чата для отправки (обязателен, если не
                указан user_id)
            user_id (int): ID пользователя для отправки (обязателен,
                если не указан chat_id). По умолчанию None
            attachments (List[Attachment | InputMedia | InputMediaBuffer
                | AttachmentUpload], optional): Список вложений.
                Может быть None.
            notify (bool): Флаг отправки уведомления. По умолчанию True.
            parse_mode (ParseMode, optional): Режим форматирования
                текста. Может быть None.
            disable_link_preview (bool, optional): Флаг генерации превью.
            sleep_after_input_media: Optional[bool] = True,

        Returns:
            Optional[SendedMessage]: Результат выполнения метода
                send_message бота.
        """

        if self.body is None:
            msg = "Невозможно переслать: поле body отсутствует у сообщения"
            raise ValueError(msg)

        return await self._ensure_bot().send_message(
            chat_id=chat_id,
            user_id=user_id,
            attachments=attachments,
            link=NewMessageLink(
                type=MessageLinkType.FORWARD, mid=self.body.mid
            ),
            notify=notify,
            parse_mode=parse_mode,
            disable_link_preview=disable_link_preview,
            sleep_after_input_media=sleep_after_input_media,
        )

    async def edit(
        self,
        text: str | None = None,
        attachments: list[
            Attachment | InputMedia | InputMediaBuffer | AttachmentUpload
        ]
        | list[Attachments]
        | None = None,
        link: NewMessageLink | None = None,
        parse_mode: ParseMode | None = None,
        *,
        notify: bool = True,
        sleep_after_input_media: bool | None = True,
    ) -> EditedMessage | None:
        """
        Редактирует текущее сообщение.

        Args:
            text (str, optional): Новый текст сообщения. Может быть None.
            attachments (List[Attachment | InputMedia | InputMediaBuffer |
                AttachmentUpload], optional): Новые вложения. Может быть None.
            link (NewMessageLink, optional): Новая связь с сообщением.
                Может быть None.
            parse_mode (ParseMode, optional): Режим форматирования текста.
                Может быть None.
            notify (bool): Флаг отправки уведомления. По умолчанию True.
            sleep_after_input_media (bool, optional): Флаг задержки
                после отправки вложений типа InputMedia. По умолчанию True.
        Returns:
            Optional[EditedMessage]: Результат выполнения метода
                edit_message бота.
        """

        if link is None and self.link:
            link = NewMessageLink(
                type=self.link.type, mid=self.link.message.mid
            )

        if (
            attachments is None
            and self.body is not None
            and self.body.attachments
        ):
            attachments = self.body.attachments

        if self.body is None:
            msg = "Невозможно редактировать: поле body отсутствует у сообщения"
            raise ValueError(msg)

        return await self._ensure_bot().edit_message(
            message_id=self.body.mid,
            text=text,
            attachments=attachments,
            link=link,
            notify=notify,
            parse_mode=parse_mode,
            sleep_after_input_media=sleep_after_input_media,
        )

    async def delete(self) -> DeletedMessage:
        """
        Удаляет текущее сообщение.

        Returns:
            DeletedMessage: Результат выполнения метода delete_message бота.
        """

        if self.body is None:
            msg = "Невозможно удалить: поле body отсутствует у сообщения"
            raise ValueError(msg)

        return await self._ensure_bot().delete_message(
            message_id=self.body.mid,
        )

    async def pin(self, *, notify: bool = True) -> PinnedMessage:
        """
        Закрепляет текущее сообщение в чате.

        Args:
            notify (bool): Флаг отправки уведомления. По умолчанию True.

        Returns:
            PinnedMessage: Результат выполнения метода pin_message бота.
        """

        if self.body is None:
            msg = "Невозможно закрепить: поле body отсутствует у сообщения"
            raise ValueError(msg)

        if self.recipient.chat_id is None:
            raise ValueError("chat_id не может быть None")

        return await self._ensure_bot().pin_message(
            chat_id=self.recipient.chat_id,
            message_id=self.body.mid,
            notify=notify,
        )


class Messages(BaseModel):
    """
    Модель списка сообщений.

    Attributes:
        messages (List[Message]): Список сообщений.
        bot (Optional[Bot]): Объект бота, исключается из сериализации.
    """

    messages: list[Message]
    bot: Any | None = Field(  # pyright: ignore[reportRedeclaration]
        default=None, exclude=True
    )

    if TYPE_CHECKING:
        bot: Bot | None  # type: ignore


class NewMessageLink(BaseModel):
    """
    Модель ссылки на новое сообщение.

    Attributes:
        type (MessageLinkType): Тип связи.
        mid (str): Идентификатор сообщения.
    """

    type: MessageLinkType
    mid: str
