from typing import TYPE_CHECKING

from .types.removed_admin import RemovedAdmin

from ..enums.http_method import HTTPMethod
from ..enums.api_path import ApiPath

from ..connection.base import BaseConnection


if TYPE_CHECKING:
    from ..bot import Bot


class RemoveAdmin(BaseConnection):
    
    """
    Класс для отмены прав администратора в чате.
    
    https://dev.max.ru/docs-api/methods/DELETE/chats/-chatId-/members/admins/-userId-

    Attributes:
        bot (Bot): Экземпляр бота.
        chat_id (int): Идентификатор чата.
        user_id (int): Идентификатор пользователя.
    """

    def __init__(
            self, 
            bot: 'Bot',
            chat_id: int,
            user_id: int
        ):
        self.bot = bot
        self.chat_id = chat_id
        self.user_id = user_id

    async def fetch(self) -> RemovedAdmin:
        
        """
        Выполняет DELETE-запрос для отмены прав администратора в чате.

        Returns:
            RemovedAdmin: Объект с результатом отмены прав администратора.
        """
        
        if self.bot is None:
            raise RuntimeError('Bot не инициализирован')
        
        return await super().request(
            method=HTTPMethod.DELETE, 
            path=ApiPath.CHATS + '/' + str(self.chat_id) + \
                  ApiPath.MEMBERS + ApiPath.ADMINS + '/' + str(self.user_id),
            model=RemovedAdmin,
            params=self.bot.params,
        ) 