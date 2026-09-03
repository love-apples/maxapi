from __future__ import annotations

from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..types.comment import Comments
from ..utils.time import to_ms

if TYPE_CHECKING:
    from datetime import datetime

    from ..bot import Bot


class GetComments(BaseConnection):
    """
    Класс для получения комментариев к посту в канале через API.

    https://dev.max.ru/docs-api/methods/GET/messages/-messageId-/comments

    Attributes:
        bot: Экземпляр бота.
        message_id: Идентификатор поста (mid).
        comment_ids: Фильтр по идентификаторам комментариев. Если
            указан, пагинация игнорируется.
        after: Начальная временная метка (Unix timestamp
            в миллисекундах).
        before: Конечная временная метка (Unix timestamp
            в миллисекундах).
        count: Максимальное число комментариев.
    """

    def __init__(
        self,
        bot: Bot,
        message_id: str,
        comment_ids: list[str] | None = None,
        after: datetime | int | None = None,
        before: datetime | int | None = None,
        count: int | None = 50,
    ):
        if len(message_id) < 1:
            raise ValueError("message_id не должен быть меньше 1 символа")

        if comment_ids is not None and not comment_ids:
            raise ValueError("comment_ids не должен быть пустым")

        if comment_ids is not None and not all(comment_ids):
            raise ValueError(
                "comment_ids не должен содержать пустые идентификаторы"
            )

        if count is not None and not (1 <= count <= 100):
            raise ValueError("count не должен быть меньше 1 или больше 100")

        super().__init__()
        self.bot = bot
        self.message_id = message_id
        self.comment_ids = comment_ids
        self.after = after
        self.before = before
        self.count = count

    async def fetch(self) -> Comments:
        """
        Выполняет GET-запрос для получения комментариев с учётом
        параметров фильтрации.

        Преобразует datetime в UNIX timestamp в миллисекундах
        при необходимости. Если указан comment_ids, параметры
        пагинации не отправляются (API их игнорирует).

        Returns:
            Comments: Объект с полученными комментариями.
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        if self.comment_ids is not None:
            params["comment_ids"] = ",".join(self.comment_ids)
        else:
            if self.after is not None:
                params["after"] = to_ms(self.after)

            if self.before is not None:
                params["before"] = to_ms(self.before)

            if self.count is not None:
                params["count"] = self.count

        response = await super().request(
            method=HTTPMethod.GET,
            path=ApiPath.MESSAGES + "/" + self.message_id + ApiPath.COMMENTS,
            model=Comments,
            params=params,
        )

        comments = cast(Comments, response)

        # recipient.post_id в схеме API помечен Nullable, поэтому
        # надёжный источник post_message_id — контекст запроса:
        # message_id, по которому запрос реально выполнен.
        for comment in comments.messages:
            comment.post_message_id = self.message_id

        return comments
