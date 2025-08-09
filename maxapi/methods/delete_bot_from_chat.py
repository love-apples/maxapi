from typing import TYPE_CHECKING

from ..methods.types.deleted_bot_from_chat import DeletedBotFromChat

from ..enums.http_method import HTTPMethod
from ..enums.api_path import ApiPath

from ..connection.base import BaseConnection


if TYPE_CHECKING:
    from ..bot import Bot


class DeleteMeFromMessage(BaseConnection):
    
    """
    Класс для удаления бота из участников указанного чата.
    
    https://dev.max.ru/docs-api/methods/DELETE/chats/-chatId-/members/me

    Attributes:
        bot (Bot): Экземпляр бота для выполнения запроса.
        chat_id (int): Идентификатор чата, из которого нужно удалить бота.
    """
    
    def __init__(
            self,
            bot: 'Bot',
            chat_id: int,
        ):
            self.bot = bot
            self.chat_id = chat_id

    async def fetch(self) -> DeletedBotFromChat:
        
        """
        Отправляет DELETE-запрос для удаления бота из чата.

        Returns:
            DeletedBotFromChat: Результат операции удаления.
        """
        
        if self.bot is None:
            raise RuntimeError('Bot не инициализирован')
        return await super().request(
            method=HTTPMethod.DELETE, 
            path=ApiPath.CHATS + '/' + str(self.chat_id) + ApiPath.MEMBERS + ApiPath.ME,
            model=DeletedBotFromChat,
            params=self.bot.params,
        )