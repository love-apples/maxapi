from __future__ import annotations

from json import JSONDecodeError, loads
from typing import TYPE_CHECKING
from uuid import uuid4

from ..enums.upload_type import UploadType
from ..exceptions.max import MaxApiError, MaxUploadFileFailed
from ..types.attachments.upload import AttachmentPayload, AttachmentUpload
from ..types.input_media import InputMedia, InputMediaBuffer

if TYPE_CHECKING:
    from ..bot import Bot
    from ..connection.base import BaseConnection


async def _get_upload_info(bot: Bot, upload_type: UploadType):
    try:
        return await bot.get_upload_url(upload_type)
    except MaxApiError as e:
        raise MaxUploadFileFailed(
            f"Ошибка при загрузке файла: code={e.code}, raw={e.raw}"
        ) from e


async def _upload_input_media(
    base_connection: BaseConnection,
    upload_url: str,
    att: InputMedia | InputMediaBuffer,
) -> str:
    if isinstance(att, InputMedia):
        return await base_connection.upload_file(
            url=upload_url,
            path=att.path,
            type=att.type,
        )

    if isinstance(att, InputMediaBuffer):
        return await base_connection.upload_file_buffer(
            filename=att.filename or str(uuid4()),
            url=upload_url,
            buffer=att.buffer,
            type=att.type,
        )

    raise TypeError(f"Unsupported media type: {type(att)!r}")


def _extract_upload_token_from_response(
    upload_type: UploadType, upload_file_response: str
) -> str:
    try:
        json_response = loads(upload_file_response)
    except JSONDecodeError as e:
        raise MaxUploadFileFailed(
            "Не удалось распарсить ответ upload-сервера"
        ) from e

    if upload_type == UploadType.FILE:
        token = json_response.get("token")
        if isinstance(token, str) and token:
            return token
        raise MaxUploadFileFailed("В ответе upload-сервера отсутствует token")

    if upload_type == UploadType.IMAGE:
        photos = json_response.get("photos")
        if not isinstance(photos, dict) or not photos:
            raise MaxUploadFileFailed(
                "В ответе upload-сервера отсутствует photos"
            )

        first_photo = next(iter(photos.values()))
        if isinstance(first_photo, dict):
            token = first_photo.get("token")
            if isinstance(token, str) and token:
                return token

        raise MaxUploadFileFailed(
            "В ответе upload-сервера отсутствует token для изображения"
        )

    raise MaxUploadFileFailed(
        f"Извлечение токена из upload-ответа не поддерживается для "
        f"типа {upload_type.value}"
    )


async def _resolve_attachment_token(
    *,
    bot: Bot,
    upload_type: UploadType,
    upload_token: str | None,
    upload_file_response: str,
) -> str:
    if upload_type in (UploadType.VIDEO, UploadType.AUDIO):
        if upload_token is None:
            raise MaxUploadFileFailed(
                "По неизвестной причине token не был получен"
            )
        return upload_token

    return _extract_upload_token_from_response(
        upload_type=upload_type,
        upload_file_response=upload_file_response,
    )


async def process_input_media(
    base_connection: BaseConnection,
    bot: Bot,
    att: InputMedia | InputMediaBuffer,
) -> AttachmentUpload:
    """
    Загружает файл вложения и формирует объект AttachmentUpload.

    Args:
        base_connection (BaseConnection): Базовое соединение для
            загрузки файла.
        bot (Bot): Экземпляр бота.
        att (InputMedia | InputMediaBuffer): Объект вложения
            для загрузки.

    Returns:
        AttachmentUpload: Загруженное вложение с токеном.
    """

    upload = await _get_upload_info(bot=bot, upload_type=att.type)
    upload_file_response = await _upload_input_media(
        base_connection=base_connection,
        upload_url=upload.url,
        att=att,
    )
    token = await _resolve_attachment_token(
        bot=bot,
        upload_type=att.type,
        upload_token=upload.token,
        upload_file_response=upload_file_response,
    )

    return AttachmentUpload(
        type=att.type, payload=AttachmentPayload(token=token)
    )


def mid_to_chatid_seq(mid: str) -> tuple[int, int]:
    """
    Декодирует строку mid в chat_id и seq.
    Формат mid: 'mid.' + 16 hex-символов (chat_id) + 16 hex-символов (seq)
    """
    hex_part = mid[4:]  # Отбрасываем префикс 'mid.'
    
    # Первые 16 символов — chat_id. MAX хранит его как signed 64-bit,
    # но в hex он представлен как unsigned. Конвертируем обратно в signed.
    chat_id_unsigned = int(hex_part[:16], 16)
    chat_id = chat_id_unsigned - (1 << 64) if chat_id_unsigned >= (1 << 63) else chat_id_unsigned
    
    # Последние 16 символов — seq. Всегда положительное 64-bit число.
    seq = int(hex_part[16:], 16)
    
    return chat_id, seq


def chatid_seq_to_mid(chat_id: int, seq: int) -> str:
    """
    Создаёт валидную строку mid из chat_id и seq.
    """
    # Битовая маска гарантирует корректное hex-представление для signed int
    # (отрицательные числа автоматически преобразуются в two's complement)
    chat_id_hex = f"{chat_id & 0xFFFFFFFFFFFFFFFF:016x}"
    seq_hex = f"{seq:016x}"
    
    return f"mid.{chat_id_hex}{seq_hex}"


def build_message_link(self, mid: str) -> str:
    """
    Генерирует прямую ссылку на сообщение в интерфейсе MAX.
    Формат: https://max.ru/c/{chat_id}/{urlsafe_base64(seq_без_padding)}
    """
    if not mid.startswith('mid.'):
        raise ValueError('mid должен начинаться с "mid."')
    
    try:
        int(mid[4:], 16)  # Валидирует только hex-символы
    except ValueError:
        raise ValueError('Содержимое после "mid." должно быть в hex-формате')

    if len(mid) != 4 + 32:
        raise ValueError('длина hex значениея mid должена быть 32 символа')

    chat_id, seq = self.mid_to_chatid_seq(mid)
    
    # 1. Преобразуем seq в 8 байт (big-endian)
    seq_bytes = seq.to_bytes(8, byteorder="big")
    # 2. Кодируем в URL-safe Base64 и убираем символы дополнения '='
    seq_b64 = base64.urlsafe_b64encode(seq_bytes).decode("ascii").rstrip("=")
    
    return f"https://max.ru/c/{chat_id}/{seq_b64}"