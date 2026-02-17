from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from ...enums.attachment import AttachmentType
from .attachment import Attachment

if TYPE_CHECKING:
    from ...bot import Bot


class VideoUrl(BaseModel):
    """
    URLs различных разрешений видео.

    Attributes:
        mp4_1080 (Optional[str]): URL видео в 1080p.
        mp4_720 (Optional[str]): URL видео в 720p.
        mp4_480 (Optional[str]): URL видео в 480p.
        mp4_360 (Optional[str]): URL видео в 360p.
        mp4_240 (Optional[str]): URL видео в 240p.
        mp4_144 (Optional[str]): URL видео в 144p.
        hls (Optional[str]): URL HLS потока.
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
        url (str): URL миниатюры.
    """

    url: str


class Video(Attachment):
    """
    Вложение с типом видео.

    Attributes:
        token (Optional[str]): Токен видео.
        urls (Optional[VideoUrl]): URLs видео разных разрешений.
        thumbnail (VideoThumbnail): Миниатюра видео.
        width (Optional[int]): Ширина видео.
        height (Optional[int]): Высота видео.
        duration (Optional[int]): Продолжительность видео в секундах.
        bot (Optional[Any]): Ссылка на экземпляр бота, не сериализуется.
    """

    type: Literal[AttachmentType.VIDEO]  # pyright: ignore[reportIncompatibleVariableOverride]
    token: str | None = None
    urls: VideoUrl | None = None
    thumbnail: VideoThumbnail
    width: int | None = None
    height: int | None = None
    duration: int | None = None
    bot: Any | None = Field(default=None, exclude=True)  # pyright: ignore[reportRedeclaration]

    if TYPE_CHECKING:
        bot: "Bot" | None  # type: ignore
