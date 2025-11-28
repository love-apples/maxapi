from typing import List, Optional

from pydantic import BaseModel


class Subscription(BaseModel):
    """
    Подписка для вебхука

    Attributes:
        url (str): URL вебхука
        time (int): Unix-время, когда была создана подписка
        update_types (List[str]): Типы обновлений, на которые подписан бот
    """

    url: str
    time: int
    update_types: Optional[List[str]] = None
