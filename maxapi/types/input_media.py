from __future__ import annotations

from ..enums.upload_type import UploadType
from ..utils.media import detect_upload_type_from_bytes


class InputMedia:
    """Класс для представления медиафайла.

    Attributes:
        path: Путь к файлу.
        type: Тип файла, определенный на основе содержимого (MIME-типа).
    """

    def __init__(self, path: str) -> None:
        """Инициализирует объект медиафайла.

        Args:
            path: Путь к файлу.
        """

        self.path = path
        self.type = self._detect_file_type(path)

    @staticmethod
    def _detect_file_type(path: str) -> UploadType:
        """Определяет тип файла на основе его содержимого.

        Args:
            path: Путь к файлу.

        Returns:
            UploadType: Тип файла (VIDEO, IMAGE, AUDIO или FILE).
        """

        with open(path, "rb") as f:
            sample = f.read(4096)

        return detect_upload_type_from_bytes(sample)


class InputMediaBuffer:
    """Класс для представления медиафайла из буфера.

    Attributes:
        buffer: Буфер с содержимым файла.
        type: Тип файла, определенный по содержимому.
        filename: Название файла.
    """

    def __init__(
        self, buffer: bytes, filename: str | None = None
    ) -> None:
        """Инициализирует объект медиафайла из буфера.

        Args:
            buffer: Буфер с содержимым файла.
            filename: Название файла (по умолчанию присваивается uuid4).
        """

        self.filename = filename
        self.buffer = buffer
        self.type = detect_upload_type_from_bytes(buffer)
