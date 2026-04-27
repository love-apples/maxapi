from pydantic import BaseModel

from ...types.subscription import Subscription


class GettedSubscriptions(BaseModel):
    """
    Ответ API с отправленным сообщением.

    Attributes:
        subscriptions: Список подписок бота.
    """

    subscriptions: list[Subscription]
