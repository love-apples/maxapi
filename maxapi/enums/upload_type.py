from enum import auto, unique

from ._compat import StrEnum


@unique
class UploadType(StrEnum):
    """
    Типы загружаемых файлов.

    Используются для указания категории контента при загрузке на сервер.

    Ограничения сервера MAX (см.
    https://dev.max.ru/docs-api/methods/POST/uploads):

    | Значение | Форматы | Лимиты |
    | --- | --- | --- |
    | image | JPG/JPEG/PNG/GIF/TIFF/BMP/HEIC | до 50 МБ, ≤7680×7680 px |
    | video | MP4, MOV, MKV, WEBM | до 250 МБ |
    | audio | MP3, WAV, M4A и др. | до 256 МБ, ≤60 мин |
    | file | TXT, DOC, PDF и др. | до 4 ГБ |

    Для `image` и `audio` оба условия проверяются одновременно.
    """

    IMAGE = auto()
    VIDEO = auto()
    AUDIO = auto()
    FILE = auto()
