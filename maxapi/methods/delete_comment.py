from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from .types.deleted_comment import DeletedComment

if TYPE_CHECKING:
    from ..bot import Bot


class DeleteComment(BaseConnection):
    """
    Класс для удаления комментария к посту в канале через API.

    https://dev.max.ru/docs-api/methods/DELETE/messages/-messageId-/comments

    Attributes:
        bot: Экземпляр бота для выполнения запроса.
        message_id: Идентификатор поста (mid), комментарий
            к которому нужно удалить.
        comment_id: Идентификатор удаляемого комментария.
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

    async def fetch(self) -> DeletedComment:
        """
        Выполняет DELETE-запрос для удаления комментария.

        Returns:
            DeletedComment: Результат операции удаления комментария.
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        params["comment_id"] = self.comment_id

        response = await super().request(
            method=HTTPMethod.DELETE,
            path=ApiPath.MESSAGES + "/" + self.message_id + ApiPath.COMMENTS,
            model=DeletedComment,
            params=params,
        )

        return cast(DeletedComment, response)
