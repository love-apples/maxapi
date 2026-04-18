from __future__ import annotations

from pathlib import Path

import puremagic

from ..enums.upload_type import UploadType

READ_FILE_CHUNK_SIZE = 4096


def detect_file_type(data: bytes) -> UploadType:
    """
    Определяет тип файла на основе его содержимого (MIME-типа).

    Args:
        data (bytes): Буфер с содержимым файла.
    Returns:
            UploadType: Определенный тип файла. Если MIME-тип не удалось
                        определить или при определении произошла ошибка,
                        возвращается ``UploadType.FILE``.
    """
    try:
        matches = puremagic.magic_string(data)
        if matches:
            mime_type = matches[0].mime_type
        else:
            mime_type = None
    except Exception:
        mime_type = None

    if mime_type is None:
        return UploadType.FILE
    if mime_type.startswith("video/"):
        return UploadType.VIDEO
    elif mime_type.startswith("image/"):
        return UploadType.IMAGE
    elif mime_type.startswith("audio/"):
        return UploadType.AUDIO
    else:
        return UploadType.FILE


def validate_uploading_type(type: UploadType | str) -> UploadType:
    if not isinstance(type, UploadType):
        try:
            return UploadType(type)
        except ValueError as e:
            allowed = ", ".join(item.value for item in UploadType)
            raise ValueError(
                f"Неверный тип загружаемого файла: {type!r}. Ожидается: {allowed}"  # noqa: E501
            ) from e

    return type


class InputMedia:
    """
    Класс для представления медиафайла.

    Attributes:
        path (str): Путь к файлу.
        type (UploadType | str | None): Тип файла, определенный на основе содержимого
            (MIME-типа).
    """  # noqa: E501

    def __init__(self, path: str, type: UploadType | str | None = None):
        """
        Инициализирует объект медиафайла.

        Args:
            path (str): Путь к файлу.
            type (UploadType | str |None): Тип файла. Если не указан,
                определяется автоматически.
        """

        self.path = path

        if type is not None:
            self.type = validate_uploading_type(type)
        else:
            self.type = detect_file_type(InputMedia._read_file_sample(path))

    @staticmethod
    def _read_file_sample(
        path: str, size: int = READ_FILE_CHUNK_SIZE
    ) -> bytes:
        with Path(path).open("rb") as f:
            return f.read(size)


class InputMediaBuffer:
    """
    Класс для представления медиафайла из буфера.

    Attributes:
        buffer (bytes): Буфер с содержимым файла.
        type (UploadType | str | None): Тип файла, определенный по содержимому.
    """

    def __init__(
        self,
        buffer: bytes,
        filename: str | None = None,
        type: UploadType | str | None = None,
    ):
        """
        Инициализирует объект медиафайла из буфера.

        Args:
            buffer (bytes): Буфер с содержимым файла.
            filename (str, optional): Название файла (по умолчанию
                присваивается uuid4).
            type (UploadType | str | None): Тип файла. Если не указан,
                определяется автоматически.
        """

        self.filename = filename
        self.buffer = buffer

        if type is not None:
            self.type = validate_uploading_type(type)
        else:
            self.type = detect_file_type(buffer)
