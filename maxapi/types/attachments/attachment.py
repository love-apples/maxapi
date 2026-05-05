from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from ...enums.attachment import AttachmentType
from ...types.attachments.buttons import InlineButtonUnion
from ...types.attachments.upload import AttachmentUpload
from ...types.users import User
from ...utils.vcf import VcfInfo, parse_vcf_info

if TYPE_CHECKING:
    from ...bot import Bot


class StickerAttachmentPayload(BaseModel):
    """
    Данные для вложения типа стикер.

    Attributes:
        url: URL стикера.
        code: Код стикера.
    """

    url: str
    code: str


class PhotoAttachmentPayload(BaseModel):
    """
    Данные для фото-вложения.

    Attributes:
        photo_id: Идентификатор фотографии.
        token: Токен для доступа к фото.
        url: URL фотографии.
    """

    photo_id: int
    token: str
    url: str


class OtherAttachmentPayload(BaseModel):
    """
    Данные для общих типов вложений (файлы и т.п.).

    Attributes:
        url: URL вложения.
        token: Опциональный токен доступа.
    """

    url: str
    token: str | None = None


class ShareAttachmentPayload(BaseModel):
    """
    Данные для вложения типа "share".

    Attributes:
        url: URL расшаренного ресурса.
        token: Токен доступа.
    """

    url: str | None = None
    token: str | None = None


class ContactAttachmentPayload(BaseModel):
    """
    Данные для контакта.

    Attributes:
        vcf_info: Информация в формате vcf.
        max_info: Дополнительная информация о пользователе.
    """

    vcf_info: str | None = ""
    hash: str | None = None
    max_info: User | None = None

    @property
    def vcf(self) -> VcfInfo:
        """Доступ к данным из `vcf_info`."""

        return parse_vcf_info(self.vcf_info or "")


class ButtonsPayload(BaseModel):
    """
    Данные для вложения с кнопками.

    Attributes:
        buttons: Двумерный список
            inline-кнопок.
    """

    buttons: list[list[InlineButtonUnion]]

    def pack(self):
        return Attachment(  # type: ignore[call-arg]
            type=AttachmentType.INLINE_KEYBOARD,
            payload=self,
        )


AttachmentPayload = (
    AttachmentUpload
    | PhotoAttachmentPayload
    | OtherAttachmentPayload
    | ShareAttachmentPayload
    | ButtonsPayload
    | ContactAttachmentPayload
    | StickerAttachmentPayload
)


class Attachment(BaseModel):
    """
    Универсальный класс вложения с типом и полезной нагрузкой.

    Attributes:
        type: Тип вложения.
        payload: Полезная нагрузка, зависит
            от типа вложения.
    """

    type: AttachmentType
    payload: AttachmentPayload | None = None
    bot: Any | None = Field(default=None, exclude=True)

    if TYPE_CHECKING:
        bot: Bot | None  # type: ignore[no-redef]

    model_config = ConfigDict(
        use_enum_values=True,
    )
