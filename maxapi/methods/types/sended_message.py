from pydantic import BaseModel

from ...types.message import Message


class SendedMessage(BaseModel):
    """
    Ответ API с отправленным сообщением.

    Attributes:
        message (Message): Объект отправленного сообщения.
    """

    message: Message
