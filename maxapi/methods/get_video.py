from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..types.attachments.video import Video

if TYPE_CHECKING:
    from ..bot import Bot


class GetVideo(BaseConnection):
    """
    Класс для получения информации о видео по его токену.

    https://dev.max.ru/docs-api/methods/GET/videos/-videoToken-

    Attributes:
        bot (Bot): Экземпляр бота для выполнения запроса.
        video_token (str): Токен видео для запроса.
    """

    def __init__(self, bot: "Bot", video_token: str):
        self.bot = bot
        self.video_token = video_token

    async def fetch(self) -> Video:
        """
        Выполняет GET-запрос для получения данных видео по токену.

        Returns:
            Video: Объект с информацией о видео.
        """

        bot = self._ensure_bot()

        response = await super().request(
            method=HTTPMethod.GET,
            path=ApiPath.VIDEOS.value + "/" + self.video_token,
            model=Video,
            params=bot.params,
        )

        return cast(Video, response)
