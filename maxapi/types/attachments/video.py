from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from ...enums.attachment import AttachmentType
from .attachment import (
    Attachment,
)

if TYPE_CHECKING:
    from ...bot import Bot


class VideoUrl(BaseModel):
    """
    URLs различных разрешений видео.

    Attributes:
        mp4_1080: URL видео в 1080p.
        mp4_720: URL видео в 720p.
        mp4_480: URL видео в 480p.
        mp4_360: URL видео в 360p.
        mp4_240: URL видео в 240p.
        mp4_144: URL видео в 144p.
        hls: URL HLS потока.
    """

    mp4_1080: str | None = None
    mp4_720: str | None = None
    mp4_480: str | None = None
    mp4_360: str | None = None
    mp4_240: str | None = None
    mp4_144: str | None = None
    hls: str | None = None


class VideoThumbnail(BaseModel):
    """
    Миниатюра видео.

    Attributes:
        photo_id: Идентификатор фото миниатюры.
        token: Токен миниатюры.
        url: URL миниатюры.
    """

    photo_id: int | None = None
    token: str | None = None
    url: str


class Video(Attachment):
    """
    Вложение с типом видео.

    Attributes:
        token: Токен видео.
        urls: URLs видео разных разрешений.
        thumbnail: Миниатюра видео.
        width: Ширина видео.
        height: Высота видео.
        duration: Продолжительность видео в секундах.
        bot: Ссылка на экземпляр бота, не сериализуется.
    """

    type: Literal[AttachmentType.VIDEO] = AttachmentType.VIDEO  # pyright: ignore[reportIncompatibleVariableOverride]
    token: str | None = None
    urls: VideoUrl | None = None
    thumbnail: VideoThumbnail | None = None
    width: int | None = None
    height: int | None = None
    duration: int | None = None
    bot: Any | None = Field(default=None, exclude=True)  # pyright: ignore[reportRedeclaration]

    if TYPE_CHECKING:
        bot: Bot | None  # type: ignore
