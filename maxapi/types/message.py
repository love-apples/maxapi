from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..enums.chat_type import ChatType
from ..enums.message_link_type import MessageLinkType
from ..enums.text_style import TextStyle
from ..types.attachments import Attachments
from ..types.bot_mixin import BotMixin
from ..types.shortcuts import ChatActionShortcutMixin, PeerShortcutMixin
from ..utils.formatting import (
    Blockquote,
    Bold,
    Code,
    Heading,
    Highlighted,
    Italic,
    Link,
    Strikethrough,
    Text,
    Underline,
    UserMention,
)
from ..utils.message_link import build_message_link
from .users import User

if TYPE_CHECKING:
    from ..bot import Bot
    from ..enums.parse_mode import ParseMode, TextFormat
    from ..methods.types.deleted_message import DeletedMessage
    from ..methods.types.deleted_pin_message import DeletedPinMessage
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
        type: Тип разметки.
        from_: Начальная позиция разметки в тексте.
        length: Длина разметки.
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
        url: URL ссылки. Может быть None.
    """

    type: Literal[TextStyle.LINK] = TextStyle.LINK
    url: str | None = None


class MarkupUserMention(MarkupElement):
    """
    Модель разметки упоминания пользователя.

    Attributes:
        user_id: Идентификатор пользователя. Может быть None.
        user_link: Ссылка на пользователя. Может быть None.
    """

    type: Literal[TextStyle.USER_MENTION] = TextStyle.USER_MENTION
    user_id: int | None = None
    user_link: str | None = None


class Recipient(BaseModel):
    """
    Модель получателя сообщения.

    Attributes:
        user_id: Идентификатор пользователя. Может быть None.
        chat_id: Идентификатор чата. Может быть None.
        chat_type: Тип получателя (диалог или чат).
    """

    user_id: int | None = None
    chat_id: int | None = None
    chat_type: ChatType


class MessageBody(BaseModel):
    """
    Модель тела сообщения.

    Attributes:
        mid: Уникальный идентификатор сообщения.
        seq: Порядковый номер сообщения.
        text: Текст сообщения. Может быть None.
        attachments: Список вложений. По умолчанию пустой список.
        markup: Список элементов разметки. По умолчанию пустой список.
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

        def _utf16_units(ch: str) -> int:
            return 2 if ord(ch) > 0xFFFF else 1

        utf16_offsets: list[int] = []
        _cum = 0
        for ch in text:
            utf16_offsets.append(_cum)
            _cum += _utf16_units(ch)

        def _utf16_to_py_index(utf16_pos: int) -> int:
            if utf16_pos <= 0:
                return 0

            for i, off in enumerate(utf16_offsets):
                if off >= utf16_pos:
                    return i
            return len(text)

        order = {
            TextStyle.QUOTE: 0,
            TextStyle.BLOCKQUOTE: 0,
            TextStyle.STRONG: 1,
            TextStyle.EMPHASIZED: 2,
            TextStyle.UNDERLINE: 3,
            TextStyle.STRIKETHROUGH: 4,
            TextStyle.MONOSPACED: 5,
            TextStyle.HIGHLIGHTED: 6,
            TextStyle.HEADING: 7,
            TextStyle.LINK: 8,
            TextStyle.USER_MENTION: 9,
        }

        char_styles: list[
            list[tuple[TextStyle, str | None | tuple[str, int]]]
        ] = []
        for i in range(len(text)):
            utf16_i = utf16_offsets[i] if i < len(utf16_offsets) else 0
            active = []
            for m in markup:
                if m.from_ <= utf16_i < m.from_ + m.length:
                    if m.type == TextStyle.LINK:
                        val = getattr(m, "url", None)
                    elif m.type == TextStyle.USER_MENTION:
                        start = _utf16_to_py_index(m.from_)
                        end = _utf16_to_py_index(m.from_ + m.length)
                        display_text = text[start:end]
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
            TextStyle.HIGHLIGHTED: Highlighted,
            TextStyle.QUOTE: Blockquote,
            TextStyle.BLOCKQUOTE: Blockquote,
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
        views: Количество просмотров сообщения.
    """

    views: int


class LinkedMessage(BaseModel):
    """
    Модель связанного сообщения.

    Attributes:
        type: Тип связи.
        sender: Отправитель связанного сообщения,
            может быть None, если связанное сообщение отправлено каналом
            https://github.com/love-apples/maxapi/issues/11.
        chat_id: Идентификатор чата. Может быть None.
        message: Тело связанного сообщения.
    """

    type: MessageLinkType
    sender: User | None = None
    chat_id: int | None = None
    message: MessageBody


class Message(
    BaseModel,
    BotMixin,
    PeerShortcutMixin,
    ChatActionShortcutMixin,
):
    """
    Модель сообщения.

    Attributes:
        sender: Отправитель сообщения, может быть None,
            если сообщение отправлено каналом
            https://github.com/love-apples/maxapi/discussions/14.
        recipient: Получатель сообщения.
        timestamp: Временная метка сообщения.
        link: Связанное сообщение. Может быть None.
        body: Содержимое сообщения.
            Текст + вложения. Может быть None, если сообщение содержит
            только пересланное сообщение
        stat: Статистика сообщения. Может быть None.
        url: URL сообщения. Может быть None.
        bot: Объект бота, исключается из сериализации.
    """

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    sender: User | None = None
    recipient: Recipient
    timestamp: int
    link: LinkedMessage | None = None
    body: MessageBody | None = None
    stat: MessageStat | None = None
    url_api: str | None = Field(
        # Поле для хранения сырого url из ответа API.
        alias="url",
        default=None,
    )
    bot: Any | None = Field(  # pyright: ignore[reportRedeclaration]
        default=None, exclude=True
    )

    if TYPE_CHECKING:
        bot: Bot | None  # type: ignore

    @property
    def url(self) -> str | None:
        """
        Прямая ссылка на сообщение в интерфейсе MAX.

        Для каналов возвращается ссылка, полученная от API. Для диалогов и
        групповых чатов ссылка строится из ``body.mid``.
        """
        if self.url_api:
            return self.url_api
        if self.body:
            return build_message_link(self.body.mid)
        return None

    def _resolve_send_target(self) -> tuple[int | None, int | None]:
        return self.recipient.chat_id, self.recipient.user_id

    def _resolve_action_chat_id(self) -> int:
        if self.recipient.chat_id is None:
            raise ValueError(
                "Невозможно отправить action: chat_id отсутствует"
            )

        return self.recipient.chat_id

    async def answer(
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
        """
        Отправляет сообщение (автозаполнение chat_id, user_id).

        Args:
            text: Текст ответа. Может быть None.
            attachments: Список вложений. Может быть None.
            link: Связь с другим сообщением.
                Может быть None.
            format: Режим форматирования текста.
                Может быть None.
            parse_mode: Режим форматирования текста.
                Может быть None.
            notify: Флаг отправки уведомления. По умолчанию True.
            disable_link_preview: Флаг генерации превью.
            sleep_after_input_media: Флаг задержки
                после отправки вложений типа InputMedia. По умолчанию True.

        Returns:
            Optional[SendedMessage]: Результат выполнения метода
                send_message бота.
        """

        return await self.send(
            text=text,
            attachments=attachments,
            link=link,
            notify=notify,
            format=format,
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
        format: TextFormat | None = None,
        parse_mode: ParseMode | None = None,
        *,
        notify: bool | None = None,
        disable_link_preview: bool | None = None,
        sleep_after_input_media: bool | None = True,
    ) -> SendedMessage | None:
        """
        Отправляет ответное сообщение (автозаполнение chat_id, user_id, link).

        Args:
            text: Текст ответа. Может быть None.
            attachments: Список вложений. Может быть None.
            notify: Флаг отправки уведомления. По умолчанию True.
            format: Режим форматирования текста.
                Может быть None.
            parse_mode: Режим форматирования текста.
                Может быть None.
            disable_link_preview: Флаг генерации превью.
            sleep_after_input_media: Флаг задержки
                после отправки вложений типа InputMedia. По умолчанию True.

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
            format=format,
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
        format: TextFormat | None = None,
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
            chat_id: ID чата для отправки (обязателен, если не
                указан user_id)
            user_id: ID пользователя для отправки (обязателен,
                если не указан chat_id). По умолчанию None
            attachments: Список вложений. Может быть None.
            notify: Флаг отправки уведомления. По умолчанию True.
            format: Режим форматирования
                текста. Может быть None.
            parse_mode: Режим форматирования
                текста. Может быть None.
            disable_link_preview: Флаг генерации превью.
            sleep_after_input_media: Флаг задержки
                после отправки вложений типа InputMedia. По умолчанию True.

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
            format=format,
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
        format: TextFormat | None = None,
        parse_mode: ParseMode | None = None,
        *,
        notify: bool = True,
        sleep_after_input_media: bool | None = True,
    ) -> EditedMessage | None:
        """
        Редактирует текущее сообщение.

        Args:
            text: Новый текст сообщения. Может быть None.
            attachments: Новые вложения. Может быть None.
            link: Новая связь с сообщением.
                Может быть None.
            format: Режим форматирования текста.
                Может быть None.
            parse_mode: Режим форматирования текста.
                Может быть None.
            notify: Флаг отправки уведомления. По умолчанию True.
            sleep_after_input_media: Флаг задержки
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
            format=format,
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
            notify: Флаг отправки уведомления. По умолчанию True.

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

    async def unpin(self) -> DeletedPinMessage:
        """
        Снимает закрепленное сообщение в чате текущего сообщения.

        Returns:
            DeletedPinMessage: Результат выполнения метода delete_pin_message.
        """

        if self.recipient.chat_id is None:
            raise ValueError("chat_id не может быть None")

        return await self._ensure_bot().delete_pin_message(
            chat_id=self.recipient.chat_id,
        )


class Messages(BaseModel):
    """
    Модель списка сообщений.

    Attributes:
        messages: Список сообщений.
        bot: Объект бота, исключается из сериализации.
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
        type: Тип связи.
        mid: Идентификатор сообщения.
    """

    type: MessageLinkType
    mid: str
