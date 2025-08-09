from typing import TYPE_CHECKING

from ..methods.types.getted_subscriptions import GettedSubscriptions

from ..enums.http_method import HTTPMethod
from ..enums.api_path import ApiPath

from ..connection.base import BaseConnection


if TYPE_CHECKING:
    from ..bot import Bot


class GetSubscriptions(BaseConnection):
    
    """
    Если ваш бот получает данные через WebHook, этот класс возвращает список всех подписок.
    
    https://dev.max.ru/docs-api/methods/GET/subscriptions
    
    Attributes:
        bot (Bot): Экземпляр бота
    """
    
    def __init__(
            self,
            bot: 'Bot',
        ):
            self.bot = bot

    async def fetch(self) -> GettedSubscriptions:
        
        """
        Отправляет запрос на получение списка всех подписок.

        Returns:
            GettedSubscriptions: Объект со списком подписок
        """
        
        if self.bot is None:
            raise RuntimeError('Bot не инициализирован')
        
        return await super().request(
            method=HTTPMethod.GET, 
            path=ApiPath.SUBSCRIPTIONS,
            model=GettedSubscriptions,
            params=self.bot.params
        )