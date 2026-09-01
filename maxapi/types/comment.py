from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from ..enums.message_link_type import MessageLinkType
from .bot_mixin import BotMixin
from .message import BaseMessageBody, NewMessageLink, Recipient
from .users import User

if TYPE_CHECKING:
    from ..bot import Bot
    from ..enums.parse_mode import TextFormat
    from ..methods.types.deleted_comment import DeletedComment
    from ..methods.types.edited_comment import EditedComment
    from ..methods.types.sended_comment import SendedComment


class CommentMessageBody(BaseMessageBody):
    """
    Модель тела комментария.

    В отличие от тела обычного сообщения не содержит вложений
    attachments.

    Attributes:
        mid: Уникальный идентификатор комментария.
        seq: Порядковый номер расположения комментария в посте.
        text: Текст комментария. Может быть None.
        markup: Список элементов разметки. По умолчанию пустой список.
    """


class CommentLinkedMessage(BaseModel):
    """
    Модель комментария, на который получен ответ.

    Attributes:
        type: Тип связанного сообщения. Для комментариев
            поддерживается только reply.
        sender: Пользователь или бот, отправивший комментарий.
            Может быть None.
        chat_id: Чат или канал, в котором сообщение было изначально
            опубликовано. Может быть None.
        message: Тело связанного комментария.
    """

    type: MessageLinkType
    sender: User | None = None
    chat_id: int | None = None
    message: CommentMessageBody


class CommentMessage(BaseModel, BotMixin):
    """
    Модель комментария к посту в канале.

    Возвращается в ответ на запросы группы /comments. В отличие от
    обычного сообщения не содержит вложений attachments и не
    поддерживает пересылку комментариев.

    Attributes:
        sender: Пользователь, отправивший комментарий. Может быть
            None, если комментарий опубликован от имени канала.
        recipient: Получатель сообщения: для комментариев — канал.
        timestamp: Время создания комментария в формате Unix
            timestamp в миллисекундах.
        link: Комментарий, на который получен ответ. Может быть None.
        body: Информация о комментарии.
        post_message_id: ID поста (mid), к которому относится
            комментарий. API не возвращает это поле в теле ответа —
            оно заполняется библиотекой из контекста запроса, когда
            комментарий получен через методы бота (get_comments,
            get_comment, send_comment). Исключается из сериализации.
        bot: Объект бота, исключается из сериализации.
    """

    sender: User | None = None
    recipient: Recipient
    timestamp: int
    link: CommentLinkedMessage | None = None
    body: CommentMessageBody
    post_message_id: str | None = Field(default=None, exclude=True)
    bot: Any | None = Field(  # pyright: ignore[reportRedeclaration]
        default=None, exclude=True
    )

    if TYPE_CHECKING:
        bot: Bot | None  # type: ignore

    def _ensure_post_message_id(self) -> str:
        if self.post_message_id is None:
            raise ValueError(
                "Неизвестен message_id поста: комментарий получен "
                "не через методы бота, заполните post_message_id "
                "вручную"
            )

        return self.post_message_id

    async def reply(
        self,
        text: str | None = None,
        format: TextFormat | None = None,
    ) -> SendedComment:
        """
        Отправляет ответ на текущий комментарий
        (автозаполнение message_id, link).

        Args:
            text: Текст комментария.
            format: Режим форматирования текста. В комментариях
                не поддерживаются упоминания и гиперссылки.

        Returns:
            SendedComment: Результат выполнения метода
                send_comment бота.
        """

        return await self._ensure_bot().send_comment(
            message_id=self._ensure_post_message_id(),
            text=text,
            link=NewMessageLink(type=MessageLinkType.REPLY, mid=self.body.mid),
            format=format,
        )

    async def edit(
        self,
        text: str | None = None,
        link: NewMessageLink | None = None,
        format: TextFormat | None = None,
    ) -> EditedComment:
        """
        Редактирует текущий комментарий
        (автозаполнение message_id, comment_id).

        Args:
            text: Новый текст комментария.
            link: Ссылка на комментарий (например, ответ).
            format: Режим форматирования текста. В комментариях
                не поддерживаются упоминания и гиперссылки.

        Returns:
            EditedComment: Результат выполнения метода
                edit_comment бота.
        """

        return await self._ensure_bot().edit_comment(
            message_id=self._ensure_post_message_id(),
            comment_id=self.body.mid,
            text=text,
            link=link,
            format=format,
        )

    async def delete(self) -> DeletedComment:
        """
        Удаляет текущий комментарий
        (автозаполнение message_id, comment_id).

        Returns:
            DeletedComment: Результат выполнения метода
                delete_comment бота.
        """

        return await self._ensure_bot().delete_comment(
            message_id=self._ensure_post_message_id(),
            comment_id=self.body.mid,
        )


class Comments(BaseModel):
    """
    Модель списка комментариев к посту.

    Attributes:
        messages: Список комментариев.
        bot: Объект бота, исключается из сериализации.
    """

    messages: list[CommentMessage]
    bot: Any | None = Field(  # pyright: ignore[reportRedeclaration]
        default=None, exclude=True
    )

    if TYPE_CHECKING:
        bot: Bot | None  # type: ignore
