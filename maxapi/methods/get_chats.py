from typing import TYPE_CHECKING, Optional

from ..types.chats import Chats

from ..enums.http_method import HTTPMethod
from ..enums.api_path import ApiPath

from ..connection.base import BaseConnection


if TYPE_CHECKING:
    from ..bot import Bot


class GetChats(BaseConnection):
    
    """
    Класс для получения списка чатов.
    
    https://dev.max.ru/docs-api/methods/GET/chats

    Attributes:
        bot (Bot): Инициализированный клиент бота.
        count (Optional[int]): Максимальное количество чатов, возвращаемых за один запрос.
        marker (Optional[int]): Маркер для продолжения пагинации.
    """
    
    def __init__(
            self, 
            bot: 'Bot',
            count: Optional[int] = None,
            marker: Optional[int] = None
        ):
        
        if count is not None and not (1 <= count <= 100):
            raise ValueError('count не должен быть меньше 1 или больше 100')
        
        self.bot = bot
        self.count = count
        self.marker = marker

    async def fetch(self) -> Chats:
        
        """
        Выполняет GET-запрос для получения списка чатов.

        Returns:
            Chats: Объект с данными по списку чатов.
        """
        
        if self.bot is None:
            raise RuntimeError('Bot не инициализирован')
        
        params = self.bot.params.copy()

        if self.count: 
            params['count'] = self.count

        if self.marker: 
            params['marker'] = self.marker

        return await super().request(
            method=HTTPMethod.GET, 
            path=ApiPath.CHATS,
            model=Chats,
            params=params
        )