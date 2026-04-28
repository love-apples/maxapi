from pydantic import BaseModel

from ...types.subscription import Subscription


class GettedSubscriptions(BaseModel):
    """
    Ответ API, возвращающий список всех подписок бота.

    Attributes:
        subscriptions: Список подписок бота.
    """

    subscriptions: list[Subscription]
