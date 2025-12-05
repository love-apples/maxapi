from __future__ import annotations

from json import loads
from typing import TYPE_CHECKING
from uuid import uuid4

from ..enums.upload_type import UploadType
from ..exceptions.max import MaxApiError, MaxUploadFileFailed
from ..types.attachments.upload import AttachmentPayload, AttachmentUpload
from ..types.input_media import InputMedia, InputMediaBuffer

if TYPE_CHECKING:
    from ..bot import Bot
    from ..connection.base import BaseConnection


async def process_input_media(
    base_connection: BaseConnection,
    bot: Bot,
    att: InputMedia | InputMediaBuffer,
) -> AttachmentUpload:
    # очень нестабильный метод независящий от модуля
    # ждем обновлений MAX API

    """
    Загружает файл вложения и формирует объект AttachmentUpload.

    Args:
        base_connection (BaseConnection): Базовое соединение для загрузки файла.
        bot (Bot): Экземпляр бота.
        att (InputMedia | InputMediaBuffer): Объект вложения для загрузки.

    Returns:
        AttachmentUpload: Загруженное вложение с токеном.
    """

    try:
        upload = await bot.get_upload_url(att.type)
    except MaxApiError as e:
        raise MaxUploadFileFailed(
            f"Ошибка при загрузке файла: code={e.code}, raw={e.raw}"
        )

    if isinstance(att, InputMedia):
        upload_file_response = await base_connection.upload_file(
            url=upload.url,
            path=att.path,
            type=att.type,
        )
    elif isinstance(att, InputMediaBuffer):
        upload_file_response = await base_connection.upload_file_buffer(
            filename=att.filename or str(uuid4()),
            url=upload.url,
            buffer=att.buffer,
            type=att.type,
        )

    token = ""

    if att.type in (UploadType.VIDEO, UploadType.AUDIO):
        if upload.token is None:
            if bot.session is not None:
                await bot.session.close()

            raise MaxUploadFileFailed(
                "По неизвестной причине token не был получен"
            )

        token = upload.token

    elif att.type == UploadType.FILE:
        json_r = loads(upload_file_response)
        token = json_r["token"]

    elif att.type == UploadType.IMAGE:
        json_r = loads(upload_file_response)
        json_r_keys = list(json_r["photos"].keys())
        token = json_r["photos"][json_r_keys[0]]["token"]

    return AttachmentUpload(
        type=att.type, payload=AttachmentPayload(token=token)
    )
