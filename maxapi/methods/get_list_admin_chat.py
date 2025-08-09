from typing import TYPE_CHECKING

from ..methods.types.getted_list_admin_chat import GettedListAdminChat

from ..enums.http_method import HTTPMethod
from ..enums.api_path import ApiPath

from ..connection.base import BaseConnection


if TYPE_CHECKING:
    from ..bot import Bot


class GetListAdminChat(BaseConnection):
    
    """
    Класс для получения списка администраторов чата через API.
    
    https://dev.max.ru/docs-api/methods/GET/chats/-chatId-/members/admins

    Attributes:
        bot (Bot): Экземпляр бота.
        chat_id (int): Идентификатор чата.
    """

    def __init__(
            self, 
            bot: 'Bot',
            chat_id: int
        ):
        self.bot = bot
        self.chat_id = chat_id

    async def fetch(self) -> GettedListAdminChat:
        
        """
        Выполняет GET-запрос для получения списка администраторов указанного чата.

        Returns:
            GettedListAdminChat: Объект с информацией о администраторах чата.
        """
        
        if self.bot is None:
            raise RuntimeError('Bot не инициализирован')
        
        return await super().request(
            method=HTTPMethod.GET, 
            path=ApiPath.CHATS.value + '/' + str(self.chat_id) + ApiPath.MEMBERS + ApiPath.ADMINS,
            model=GettedListAdminChat,
            params=self.bot.params
        )