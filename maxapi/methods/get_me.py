from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..types.users import User

if TYPE_CHECKING:
    from ..bot import Bot


class GetMe(BaseConnection):
    """
    Возвращает информацию о текущем боте, который идентифицируется с помощью токена доступа.
    Метод возвращает ID бота, его имя и аватар (если есть).

    https://dev.max.ru/docs-api/methods/GET/me

    Args:
        bot (Bot): Экземпляр бота для выполнения запроса.
    """

    def __init__(self, bot: "Bot"):
        self.bot = bot

    async def fetch(self) -> User:
        """
        Выполняет GET-запрос для получения данных о боте.

        Returns:
            User: Объект пользователя с полной информацией.
        """

        bot = self._ensure_bot()

        response = await super().request(
            method=HTTPMethod.GET,
            path=ApiPath.ME,
            model=User,
            params=bot.params,
        )

        return cast(User, response)
