from typing import List

from pydantic import BaseModel

from ...types.subscription import Subscription


class GettedSubscriptions(BaseModel):
    """
    Ответ API с отправленным сообщением.

    Attributes:
        message (Message): Объект отправленного сообщения.
    """

    subscriptions: List[Subscription]
