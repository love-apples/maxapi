from enum import Enum


class UploadType(str, Enum):
    """
    Типы загружаемых файлов.

    Используются для указания категории контента при загрузке на сервер.
    """

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
