"""
Ограничения MAX API на загрузку медиафайлов.

Значения взяты из документации метода `POST /uploads`:
https://dev.max.ru/docs-api/methods/POST/uploads

| Тип     | Форматы                          | Лимиты                 |
| ------- | -------------------------------- | ---------------------- |
| `image` | JPG/JPEG/PNG/GIF/TIFF/BMP/HEIC   | до 50 МБ, ≤7680×7680 px |
| `video` | MP4, MOV, MKV, WEBM              | до 250 МБ              |
| `audio` | MP3, WAV, M4A и др.              | до 256 МБ, ≤60 мин     |
| `file`  | TXT, DOC, PDF и др.              | до 4 ГБ                |

Для `image` и `audio` оба условия должны выполняться одновременно.
Списки форматов не исчерпывающие: MAX принимает и другие
распространённые форматы, здесь перечислены только явно указанные
в документации.

Единицы измерения — явное допущение библиотеки. Документация MAX не
уточняет, двоичные единицы имеются в виду или десятичные; здесь
принимаются двоичные (МБ = 1024 ** 2, ГБ = 1024 ** 3). Если сервер
трактует их как десятичные, файлы в диапазоне ~47.7–50 MiB
предупреждения не получат, хотя сервер может их отклонить.

Заявленный лимит для `file` — 4 ГБ — это лимит сервера, а не
библиотеки. `BaseConnection.upload_file` читает файл целиком в память
перед отправкой, поэтому практический потолок ограничен доступной
процессу оперативной памятью и обычно заметно ниже.

Проверка размера (`check_upload_size`) **не бросает исключений**: это
осознанное решение. Ограничения на стороне API могут меняться, и
библиотека не должна блокировать загрузку валидных файлов. При
превышении лимита пишется предупреждение в логгер `bot`, а решение
остаётся за сервером MAX. Проверка вызывается автоматически из
`BaseConnection.upload_file` и `BaseConnection.upload_file_buffer`,
то есть на любом пути загрузки.

Разрешение изображений и длительность аудио не проверяются: для этого
потребовались бы внешние зависимости (декодеры медиа).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..enums.upload_type import UploadType
from ..loggers import logger_bot

__all__ = [
    "UPLOAD_LIMITS",
    "UploadLimits",
    "check_upload_size",
]

# Двоичные единицы — допущение библиотеки: документация MAX не
# уточняет, двоичные это единицы или десятичные (см. docstring модуля).
MB = 1024 * 1024
GB = 1024**3


@dataclass(frozen=True)
class UploadLimits:
    """
    Ограничения на загрузку файла одного типа.

    Attributes:
        formats: Форматы файлов, явно указанные в документации MAX.
            Список не исчерпывающий.
        max_size: Максимальный размер файла в байтах
            (МБ = 1024 * 1024, ГБ = 1024 ** 3).
        max_dimensions: Максимальные размеры изображения
            (ширина, высота) в пикселях, если ограничение есть.
        max_duration: Максимальная длительность в секундах,
            если ограничение есть.
    """

    formats: tuple[str, ...]
    max_size: int
    max_dimensions: tuple[int, int] | None = None
    max_duration: int | None = None


UPLOAD_LIMITS: dict[UploadType, UploadLimits] = {
    UploadType.IMAGE: UploadLimits(
        formats=("JPG", "JPEG", "PNG", "GIF", "TIFF", "BMP", "HEIC"),
        max_size=50 * MB,
        max_dimensions=(7680, 7680),
    ),
    UploadType.VIDEO: UploadLimits(
        formats=("MP4", "MOV", "MKV", "WEBM"),
        max_size=250 * MB,
    ),
    UploadType.AUDIO: UploadLimits(
        formats=("MP3", "WAV", "M4A"),
        max_size=256 * MB,
        max_duration=60 * 60,
    ),
    UploadType.FILE: UploadLimits(
        formats=("TXT", "DOC", "PDF"),
        max_size=4 * GB,
    ),
}


def _format_size(size: int) -> str:
    """
    Форматирует размер в байтах в человекочитаемую строку.

    Args:
        size: Размер в байтах.

    Returns:
        Размер в МБ или ГБ с одним знаком после запятой.
    """
    if size >= GB:
        return f"{size / GB:.1f} ГБ"
    return f"{size / MB:.1f} МБ"


def check_upload_size(
    size: int,
    type: UploadType | str,
    *,
    name: str | None = None,
) -> bool:
    """
    Проверяет размер файла против лимитов MAX API.

    Исключений не бросает: лимиты на стороне API могут меняться, и
    библиотека не должна блокировать загрузку валидных файлов. При
    превышении лимита пишется предупреждение в логгер `bot`.
    Неизвестный тип загрузки считается допустимым — решение
    остаётся за сервером MAX.

    Args:
        size: Размер файла в байтах.
        type: Тип загружаемого файла или его строковое значение.
        name: Имя файла для сообщения в логе.

    Returns:
        True, если размер в пределах лимита, иначе False.
    """
    if not isinstance(type, UploadType):
        try:
            type = UploadType(type)
        except ValueError:
            return True

    limits = UPLOAD_LIMITS.get(type)
    if limits is None or size <= limits.max_size:
        return True

    file_desc = f" {name}" if name else ""
    logger_bot.warning(
        "Файл%s типа %s превышает лимит загрузки MAX: "
        "%s (%d байт) > %s (%d байт). "
        "Сервер может отклонить загрузку.",
        file_desc,
        type.value,
        _format_size(size),
        size,
        _format_size(limits.max_size),
        limits.max_size,
    )
    return False
