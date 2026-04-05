from enum import auto, unique

from ._compat import StrEnum


@unique
class UploadType(StrEnum):
    """
    Типы загружаемых файлов.

    Используются для указания категории контента при загрузке на сервер.
    """

    IMAGE = auto()
    VIDEO = auto()
    AUDIO = auto()
    FILE = auto()
