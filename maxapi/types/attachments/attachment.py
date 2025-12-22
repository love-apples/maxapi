from typing import TYPE_CHECKING, Any, List, Optional, Union

from pydantic import BaseModel, Field

from ...enums.attachment import AttachmentType
from ...types.attachments.buttons import InlineButtonUnion
from ...types.attachments.upload import AttachmentUpload
from ...types.users import User

if TYPE_CHECKING:
    from ...bot import Bot


class StickerAttachmentPayload(BaseModel):
    """
    Данные для вложения типа стикер.

    Attributes:
        url (str): URL стикера.
        code (str): Код стикера.
    """

    url: str
    code: str


class PhotoAttachmentPayload(BaseModel):
    """
    Данные для фото-вложения.

    Attributes:
        photo_id (int): Идентификатор фотографии.
        token (str): Токен для доступа к фото.
        url (str): URL фотографии.
    """

    photo_id: int
    token: str
    url: str


class OtherAttachmentPayload(BaseModel):
    """
    Данные для общих типов вложений (файлы и т.п.).

    Attributes:
        url (str): URL вложения.
        token (Optional[str]): Опциональный токен доступа.
    """

    url: str
    token: Optional[str] = None


class ContactAttachmentPayload(BaseModel):
    """
    Данные для контакта.

    Attributes:
        vcf_info (Optional[str]): Информация в формате vcf.
        max_info (Optional[User]): Дополнительная информация о пользователе.
    """

    vcf_info: str = ""  # для корректного определения
    max_info: Optional[User] = None


class ButtonsPayload(BaseModel):
    """
    Данные для вложения с кнопками.

    Attributes:
        buttons (List[List[InlineButtonUnion]]): Двумерный список inline-кнопок.
    """

    buttons: List[List[InlineButtonUnion]]

    def pack(self):
        return Attachment(type=AttachmentType.INLINE_KEYBOARD, payload=self)  # type: ignore


class Attachment(BaseModel):
    """
    Универсальный класс вложения с типом и полезной нагрузкой.

    Attributes:
        type (AttachmentType): Тип вложения.
        payload (Optional[Union[...] ]): Полезная нагрузка, зависит от типа вложения.
    """

    type: AttachmentType
    payload: Optional[
        Union[
            AttachmentUpload,
            PhotoAttachmentPayload,
            OtherAttachmentPayload,
            ButtonsPayload,
            ContactAttachmentPayload,
            StickerAttachmentPayload,
        ]
    ] = None
    bot: Optional[Any] = Field(  # pyright: ignore[reportRedeclaration]
        default=None, exclude=True
    )

    if TYPE_CHECKING:
        bot: Optional[Bot]  # type: ignore

    class Config:
        use_enum_values = True
