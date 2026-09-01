from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..enums.parse_mode import TextFormat
from .types.edited_comment import EditedComment

if TYPE_CHECKING:
    from ..bot import Bot
    from ..types.message import NewMessageLink


class EditComment(BaseConnection):
    """
    Класс для редактирования комментария к посту в канале через API.

    https://dev.max.ru/docs-api/methods/PUT/messages/-messageId-/comments

    Attributes:
        bot: Экземпляр бота для выполнения запроса.
        message_id: Идентификатор поста (mid), комментарий
            к которому нужно отредактировать.
        comment_id: Идентификатор редактируемого комментария.
        text: Новый текст комментария.
        link: Ссылка на комментарий (например, ответ).
        format: Режим форматирования текста
            (например, Markdown, HTML). В комментариях не
            поддерживаются упоминания и гиперссылки.
    """

    def __init__(
        self,
        bot: Bot,
        message_id: str,
        comment_id: str,
        text: str | None = None,
        link: NewMessageLink | None = None,
        format: TextFormat | None = None,
    ):
        if len(message_id) < 1:
            raise ValueError("message_id не должен быть меньше 1 символа")

        if len(comment_id) < 1:
            raise ValueError("comment_id не должен быть меньше 1 символа")

        if text is not None and not (len(text) < 4000):
            raise ValueError("text должен быть меньше 4000 символов")

        # Поддержка передачи строки вместо enum: пользователь может
        # передать "html" или TextFormat.HTML — внутри всегда храним
        # enum, чтобы .value работал без ошибок.
        if isinstance(format, str) and not isinstance(format, TextFormat):
            format = TextFormat(format)

        super().__init__()
        self.bot = bot
        self.message_id = message_id
        self.comment_id = comment_id
        self.text = text
        self.link = link
        self.format = format

    async def fetch(self) -> EditedComment:
        """
        Выполняет PUT-запрос для редактирования комментария.

        Returns:
            EditedComment: Результат операции редактирования.
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        params["comment_id"] = self.comment_id

        json: dict[str, Any] = {}

        if self.text is not None:
            json["text"] = self.text

        if self.link is not None:
            json["link"] = self.link.model_dump()

        if self.format is not None:
            json["format"] = self.format

        response = await super().request(
            method=HTTPMethod.PUT,
            path=ApiPath.MESSAGES + "/" + self.message_id + ApiPath.COMMENTS,
            model=EditedComment,
            params=params,
            json=json,
        )

        return cast(EditedComment, response)
