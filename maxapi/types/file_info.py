from typing import Literal

from pydantic import BaseModel, ConfigDict


class FileInfo(BaseModel):
    """
    Метаинформация о медиафайле.

    Attributes:
        url: URL или путь к источнику.
        mime_type: MIME-тип (по сигнатуре или из заголовка).
        file_name: Имя файла.
        file_size: Размер в байтах.
        width: Ширина кадра (изображение/видео).
        height: Высота кадра (изображение/видео).
        duration: Длительность в секундах (аудио/видео).
        fps: Частота кадров (видео).
        sample_rate: Частота дискретизации (аудио), Гц.
        bitrate_nominal: Номинальный битрейт из метаданных, кбит/с.
        bitrate_avg: Средний битрейт (размер / длительность), кбит/с.
        error_desc: Описание ошибки или предупреждения.
        format: Определённый формат контейнера/кодека (по сигнатуре).
    """

    model_config = ConfigDict(frozen=True)

    url: str
    mime_type: str = ""
    file_name: str = ""
    file_size: int | None = None
    width: int | None = None
    height: int | None = None
    duration: float | None = None
    fps: float | None = None
    sample_rate: int | None = None
    bitrate_nominal: int | None = None
    bitrate_avg: int | None = None
    error_desc: str = ""
    format: (
        Literal[
            "PNG",
            "JPEG",
            "GIF",
            "WEBP",
            "WEBP/VP8X",
            "WEBP/VP8",
            "WEBP/VP8L",
            "MP4",
            "AVI",
            "MKV",
            "WEBM",
            "OGG",
            "OGV",
            "M4A",
            "MP3",
            "AAC",
            "WAV",
            "WMA",
            "FLAC",
        ]
        | None
    ) = None

    @property
    def has_dimensions(self) -> bool:
        """True, если известны ширина и высота."""
        return self.width is not None and self.height is not None

    @property
    def is_image(self) -> bool:
        """True, если MIME-тип относится к изображению."""
        return self.mime_type.startswith("image/")

    @property
    def is_audio(self) -> bool:
        """True, если MIME-тип относится к аудио."""
        return self.mime_type.startswith("audio/")

    @property
    def is_video(self) -> bool:
        """True, если MIME-тип относится к видео."""
        return self.mime_type.startswith("video/")

    @property
    def file_size_human(self) -> str:
        """Размер файла в человекочитаемом виде."""
        if self.file_size is None:
            return "неизвестно"
        if self.file_size < 1024:
            return f"{self.file_size} байт"
        if self.file_size < 1_048_576:
            return f"{self.file_size / 1024:.0f} КБ"
        if self.file_size < 1_073_741_824:
            return f"{self.file_size / 1_048_576:.1f} МБ"
        return f"{self.file_size / 1_073_741_824:.2f} ГБ"

    @property
    def status(self) -> Literal["ok", "partial", "error", "unknown"]:
        """
        Степень полноты метаданных.

        Returns:
            ``ok``      — ключевые поля для типа медиа заполнены;
            ``partial`` — часть полей отсутствует;
            ``error``   — ошибка получения данных;
            ``unknown`` — тип медиа не распознан.
        """
        if self.error_desc and not self.format:
            return "error"

        if self.is_image:
            if self.width and self.height:
                return "ok"
            return "partial"

        elif self.is_audio:
            if self.duration and self.sample_rate:
                return "ok"
            return "partial"

        elif self.is_video:
            if self.duration and self.width and self.fps:
                return "ok"
            return "partial"
        else:
            return "unknown"

    def __eq__(self, other: object) -> bool:
        """Сравнение без учёта ``url`` и ``file_name``."""
        if not isinstance(other, FileInfo):
            return NotImplemented
        s = self.model_dump()
        o = other.model_dump()
        del s["url"]
        del o["url"]
        del s["file_name"]
        del o["file_name"]
        return s == o

    def __str__(self) -> str:
        """Форматированная строка для вывода пользователю."""
        lines = []
        if self.file_name:
            lines.append(f"Имя файла: {self.file_name}")
        else:
            lines.append("[Без имени]")
        lines.append(f"Размер: {self.file_size_human}")
        if self.format:
            lines.append(f"Формат: {self.format}")
        if self.width and self.height:
            lines.append(f"Размеры: {self.width}×{self.height} пикс")
        if self.duration:
            lines.append(f"Длительность: {self.duration} сек")
        if self.fps:
            lines.append(f"Частота кадров: {self.fps} к/с")
        if self.sample_rate:
            lines.append(f"Аудио: {self.sample_rate} Гц")
        if self.bitrate_nominal:
            lines.append(
                f"Битрейт (номинальный): {self.bitrate_nominal} кбит/с"
            )
        if self.bitrate_avg:
            lines.append(f"Битрейт (средний): {self.bitrate_avg} кбит/с")
        if self.error_desc:
            lines.append(f"⚠️ {self.error_desc}")

        return "\n".join(lines)
