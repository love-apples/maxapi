from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..enums.parse_mode import TextFormat
from .types.sended_comment import SendedComment

if TYPE_CHECKING:
    from ..bot import Bot
    from ..types.message import NewMessageLink


class SendComment(BaseConnection):
    """
    Класс для отправки комментария к посту в канале через API.

    https://dev.max.ru/docs-api/methods/POST/messages/-messageId-/comments

    Attributes:
        bot: Экземпляр бота для выполнения запроса.
        message_id: Идентификатор поста (mid), к которому
            относится комментарий.
        text: Текст комментария.
        link: Ссылка на комментарий (например, ответ).
        format: Режим форматирования текста
            (например, Markdown, HTML). В комментариях не
            поддерживаются упоминания и гиперссылки.
    """

    def __init__(
        self,
        bot: Bot,
        message_id: str,
        text: str | None = None,
        link: NewMessageLink | None = None,
        format: TextFormat | None = None,
    ):
        if len(message_id) < 1:
            raise ValueError("message_id не должен быть меньше 1 символа")

        if text is not None and not (len(text) < 4000):
            raise ValueError("text должен быть меньше 4000 символов")

        if text is None and link is None:
            raise ValueError(
                "Нужно передать хотя бы один из параметров: text или link"
            )

        # Поддержка передачи строки вместо enum: пользователь может
        # передать "html" или TextFormat.HTML — внутри всегда храним
        # enum, чтобы .value работал без ошибок.
        if isinstance(format, str) and not isinstance(format, TextFormat):
            format = TextFormat(format)

        super().__init__()
        self.bot = bot
        self.message_id = message_id
        self.text = text
        self.link = link
        self.format = format

    async def fetch(self) -> SendedComment:
        """
        Выполняет POST-запрос для отправки комментария.

        Returns:
            SendedComment: Объект с отправленным комментарием.
        """

        bot = self._ensure_bot()

        json: dict[str, Any] = {}

        if self.text is not None:
            json["text"] = self.text

        if self.link is not None:
            json["link"] = self.link.model_dump()

        if self.format is not None:
            json["format"] = self.format

        response = await super().request(
            method=HTTPMethod.POST,
            path=ApiPath.MESSAGES + "/" + self.message_id + ApiPath.COMMENTS,
            model=SendedComment,
            params=bot.params,
            json=json,
        )

        sended_comment = cast(SendedComment, response)

        sended_comment.message.post_message_id = self.message_id

        return sended_comment
