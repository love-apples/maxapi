from typing import TYPE_CHECKING

from ..types.chats import ChatMember

from ..enums.http_method import HTTPMethod
from ..enums.api_path import ApiPath

from ..connection.base import BaseConnection


if TYPE_CHECKING:
    from ..bot import Bot


class GetMeFromChat(BaseConnection):
    
    """
    Класс для получения информации о текущем боте в конкретном чате.
    
    https://dev.max.ru/docs-api/methods/GET/chats/-chatId-/members/me

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

    async def fetch(self) -> ChatMember:
        
        """
        Выполняет GET-запрос для получения информации о боте в указанном чате.

        Returns:
            ChatMember: Информация о боте как участнике чата.
        """
        
        if self.bot is None:
            raise RuntimeError('Bot не инициализирован')
        
        return await super().request(
            method=HTTPMethod.GET, 
            path=ApiPath.CHATS + '/' + str(self.chat_id) + ApiPath.MEMBERS + ApiPath.ME,
            model=ChatMember,
            params=self.bot.params
        )