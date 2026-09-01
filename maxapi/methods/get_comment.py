from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..types.comment import CommentMessage

if TYPE_CHECKING:
    from ..bot import Bot


class GetComment(BaseConnection):
    """
    Класс для получения комментария к посту в канале по его ID.

    https://dev.max.ru/docs-api/methods/GET/messages/-messageId-/comments/-commentId-

    Attributes:
        bot: Экземпляр бота.
        message_id: Идентификатор поста (mid).
        comment_id: Идентификатор комментария (mid).
    """

    def __init__(
        self,
        bot: Bot,
        message_id: str,
        comment_id: str,
    ):
        if len(message_id) < 1:
            raise ValueError("message_id не должен быть меньше 1 символа")

        if len(comment_id) < 1:
            raise ValueError("comment_id не должен быть меньше 1 символа")

        super().__init__()
        self.bot = bot
        self.message_id = message_id
        self.comment_id = comment_id

    async def fetch(self) -> CommentMessage:
        """
        Выполняет GET-запрос для получения комментария.

        Returns:
            CommentMessage: Объект с полученным комментарием.
        """

        bot = self._ensure_bot()

        response = await super().request(
            method=HTTPMethod.GET,
            path=ApiPath.MESSAGES
            + "/"
            + self.message_id
            + ApiPath.COMMENTS
            + "/"
            + self.comment_id,
            model=CommentMessage,
            params=bot.params,
        )

        comment = cast(CommentMessage, response)

        comment.post_message_id = self.message_id

        return comment
