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

    Ограничения сервера MAX на загружаемые файлы (по типам):

    | Тип | Форматы | Лимиты |
    | --- | --- | --- |
    | image | JPG/JPEG/PNG/GIF/TIFF/BMP/HEIC | до 50 МБ, ≤7680×7680 px |
    | video | MP4, MOV, MKV, WEBM | до 250 МБ |
    | audio | MP3, WAV, M4A и др. | до 256 МБ, ≤60 мин |
    | file | TXT, DOC, PDF и др. | до 4 ГБ |

    Для `image` и `audio` оба условия (размер и вторая
    величина) проверяются одновременно — должны выполняться
    оба. Библиотека при загрузке через `bot.upload_media`
    проверяет только размер и лишь предупреждает в логе при
    превышении; окончательную проверку выполняет сервер MAX.

    Attributes:
        bot: Экземпляр бота для выполнения запроса.
        type: Тип загружаемого файла (например, image,
            video и т.д.).
    """

    def __init__(self, bot: "Bot", type: UploadType):
        super().__init__()
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
