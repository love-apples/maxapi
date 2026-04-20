from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..methods.types.getted_list_admin_chat import GettedListAdminChat

if TYPE_CHECKING:
    from ..bot import Bot


class GetListAdminChat(BaseConnection):
    """
    Класс для получения списка администраторов чата через API.

    https://dev.max.ru/docs-api/methods/GET/chats/-chatId-/members/admins

    Attributes:
        bot (Bot): Экземпляр бота.
        chat_id (int): Идентификатор чата.
        marker (Optional[int]): Маркер для пагинации. По умолчанию None.
    """

    def __init__(
        self,
        bot: "Bot",
        chat_id: int,
        marker: int | None = None,
    ):
        super().__init__()
        self.bot = bot
        self.chat_id = chat_id
        self.marker = marker

    async def fetch(self) -> GettedListAdminChat:
        """
        Выполняет GET-запрос для получения списка администраторов
        указанного чата.

        Returns:
            GettedListAdminChat: Объект с информацией о администраторах
                чата.
        """

        bot = self._ensure_bot()
        params = bot.params.copy()

        if self.marker is not None:
            params["marker"] = self.marker

        response = await super().request(
            method=HTTPMethod.GET,
            path=ApiPath.CHATS.value
            + "/"
            + str(self.chat_id)
            + ApiPath.MEMBERS
            + ApiPath.ADMINS,
            model=GettedListAdminChat,
            params=params,
        )

        return cast(GettedListAdminChat, response)
