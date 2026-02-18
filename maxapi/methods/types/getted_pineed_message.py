from pydantic import BaseModel

from ...types.message import Message


class GettedPin(BaseModel):
    """
    Ответ API с информацией о закреплённом сообщении.

    Attributes:
        message (Optional[Message]): Закреплённое сообщение, если оно есть.
    """

    message: Message | None = None
