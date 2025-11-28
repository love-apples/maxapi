from __future__ import annotations

import puremagic

from ..enums.upload_type import UploadType


class InputMedia:
    """
    Класс для представления медиафайла.

    Attributes:
        path (str): Путь к файлу.
        type (UploadType): Тип файла, определенный на основе содержимого (MIME-типа).
    """

    def __init__(self, path: str):
        """
        Инициализирует объект медиафайла.

        Args:
            path (str): Путь к файлу.
        """

        self.path = path
        self.type = self.__detect_file_type(path)

    def __detect_file_type(self, path: str) -> UploadType:
        """
        Определяет тип файла на основе его содержимого (MIME-типа).

        Args:
            path (str): Путь к файлу.

        Returns:
            UploadType: Тип файла (VIDEO, IMAGE, AUDIO или FILE).
        """

        with open(path, "rb") as f:
            sample = f.read(4096)

        try:
            matches = puremagic.magic_string(sample)
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


class InputMediaBuffer:
    """
    Класс для представления медиафайла из буфера.

    Attributes:
        buffer (bytes): Буфер с содержимым файла.
        type (UploadType): Тип файла, определенный по содержимому.
    """

    def __init__(self, buffer: bytes, filename: str | None = None):
        """
        Инициализирует объект медиафайла из буфера.

        Args:
            buffer (IO): Буфер с содержимым файла.
            filename (str): Название файла (по умолчанию присваивается uuid4).
        """

        self.filename = filename
        self.buffer = buffer
        self.type = self.__detect_file_type(buffer)

    def __detect_file_type(self, buffer: bytes) -> UploadType:
        try:
            matches = puremagic.magic_string(buffer)
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
