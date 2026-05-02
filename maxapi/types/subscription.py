from pydantic import BaseModel


class Subscription(BaseModel):
    """
    Подписка для вебхука

    Attributes:
        url: URL вебхука
        time: Unix-время, когда была создана подписка
        update_types: Типы обновлений, на которые подписан бот
    """

    url: str
    time: int
    update_types: list[str] | None = None
