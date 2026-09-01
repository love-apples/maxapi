from enum import auto, unique

from ._compat import StrEnum


@unique
class UploadType(StrEnum):
    """
    Типы загружаемых файлов.

    Используются для указания категории контента при загрузке на сервер.

    Ограничения на размер/формат по типам — см.
    `maxapi.utils.upload_limits.UPLOAD_LIMITS` и
    https://dev.max.ru/docs-api/methods/POST/uploads.
    """

    IMAGE = auto()
    VIDEO = auto()
    AUDIO = auto()
    FILE = auto()
