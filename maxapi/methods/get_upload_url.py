from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..enums.upload_type import UploadType
from ..methods.types.getted_upload_url import GettedUploadUrl

if TYPE_CHECKING:
    from ..bot import Bot


class GetUploadURL(BaseConnection):
    """
    Класс для получения URL загрузки файла определённого типа.

    https://dev.max.ru/docs-api/methods/POST/uploads

    Attributes:
        bot (Bot): Экземпляр бота для выполнения запроса.
        type (UploadType): Тип загружаемого файла (например, image, video и т.д.).
    """

    def __init__(self, bot: "Bot", type: UploadType):
        self.bot = bot
        self.type = type

    async def fetch(self) -> GettedUploadUrl:
        """
        Выполняет POST-запрос для получения URL загрузки файла.

        Возвращает объект с данными URL.

        Returns:
            GettedUploadUrl: Результат с URL для загрузки.
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        params["type"] = self.type.value

        response = await super().request(
            method=HTTPMethod.POST,
            path=ApiPath.UPLOADS,
            model=GettedUploadUrl,
            params=params,
        )

        return cast(GettedUploadUrl, response)
