from typing import Optional, Tuple

from .update import Update

from ...types.message import Message


class MessageEdited(Update):
    
    """
    Обновление, сигнализирующее об изменении сообщения.

    Attributes:
        message (Message): Объект измененного сообщения.
    """
    
    message: Message
    
    def get_ids(self) -> Tuple[Optional[int], Optional[int]]:
        
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            Tuple[Optional[int], Optional[int]]: Идентификаторы чата и пользователя.
        """
        
        return (self.message.recipient.chat_id, self.message.recipient.user_id)