from typing import TYPE_CHECKING, List, Optional, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..methods.types.getted_members_chat import GettedMembersChat

if TYPE_CHECKING:
    from ..bot import Bot


class GetMembersChat(BaseConnection):
    """
    Класс для получения списка участников чата через API.

    https://dev.max.ru/docs-api/methods/GET/chats/-chatId-/members

    Attributes:
        bot (Bot): Экземпляр бота для выполнения запроса.
        chat_id (int): Идентификатор чата.
        user_ids (Optional[List[str]]): Список ID пользователей для фильтрации. По умолчанию None.
        marker (Optional[int]): Маркер для пагинации (начальная позиция). По умолчанию None.
        count (Optional[int]): Максимальное количество участников для получения. По умолчанию None.

    """

    def __init__(
        self,
        bot: "Bot",
        chat_id: int,
        user_ids: Optional[List[int]] = None,
        marker: Optional[int] = None,
        count: Optional[int] = None,
    ):
        if count is not None and not (1 <= count <= 100):
            raise ValueError("count не должен быть меньше 1 или больше 100")

        self.bot = bot
        self.chat_id = chat_id
        self.user_ids = user_ids
        self.marker = marker
        self.count = count

    async def fetch(self) -> GettedMembersChat:
        """
        Выполняет GET-запрос для получения участников чата с опциональной фильтрацией.

        Формирует параметры запроса с учётом фильтров и передаёт их базовому методу.

        Returns:
            GettedMembersChat: Объект с данными по участникам чата.
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        if self.user_ids:
            params["user_ids"] = ",".join(
                [str(user_id) for user_id in self.user_ids]
            )

        if self.marker:
            params["marker"] = self.marker
        if self.count:
            params["count"] = self.count

        response = await super().request(
            method=HTTPMethod.GET,
            path=ApiPath.CHATS.value
            + "/"
            + str(self.chat_id)
            + ApiPath.MEMBERS,
            model=GettedMembersChat,
            params=params,
        )

        return cast(GettedMembersChat, response)
