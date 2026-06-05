"""
Скачивание медиа из входящих сообщений.

Демонстрирует:
- автоматическое сохранение первого входящего вложения через download_file()
- /bytes ответом на медиа — скачать вложение в bytes и показать размер
- /stream ответом на медиа — скачать вложение в BytesIO и показать имя

Запуск:
    MAX_BOT_TOKEN=your_token python 14_download_media_bot.py
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

with contextlib.suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv()

from maxapi import Bot, Dispatcher, F
from maxapi.enums.sender_action import SenderAction
from maxapi.filters.command import Command, CommandStart
from maxapi.types.attachments.video import Video

if TYPE_CHECKING:
    from maxapi.types.attachments import Attachments
    from maxapi.types.updates.message_created import MessageCreated

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot()
dp = Dispatcher()

DOWNLOAD_DIR = Path("media_downloads")


def _get_attachment_url(attachment: Attachments) -> str | None:
    """Получить URL для скачивания из поддерживаемого вложения."""

    payload = getattr(attachment, "payload", None)
    url = getattr(payload, "url", None)
    if isinstance(url, str) and url:
        return url

    if isinstance(attachment, Video) and attachment.urls is not None:
        for attr in (
            "mp4_720",
            "mp4_480",
            "mp4_360",
            "mp4_240",
            "mp4_144",
            "mp4_1080",
            "hls",
        ):
            video_url = getattr(attachment.urls, attr, None)
            if video_url:
                return video_url

    return None


def _get_first_attachment_url(event: MessageCreated) -> str | None:
    body = event.message.body
    attachments = body.attachments if body else None
    if not attachments:
        return None

    return _get_attachment_url(attachments[0])


def _get_reply_attachment_url(event: MessageCreated) -> str | None:
    link = event.message.link
    replied_body = link.message if link else None
    attachments = replied_body.attachments if replied_body else None
    if not attachments:
        return None

    return _get_attachment_url(attachments[0])


async def _answer_reply_required(event: MessageCreated) -> str | None:
    url = _get_reply_attachment_url(event)
    if url is None:
        await event.message.answer(
            "Ответьте этой командой на сообщение с медиа или файлом."
        )
        return None

    return url


@dp.message_created(CommandStart())
async def on_start(event: MessageCreated) -> None:
    """Показать подсказку."""

    await event.message.answer(
        "Пришлите файл, фото, аудио, видео или стикер — я сохраню первое "
        "вложение в media_downloads.\n\n"
        "Команды ответом на сообщение с вложением:\n"
        "/bytes — скачать в bytes и показать размер\n"
        "/stream — скачать в BytesIO и показать имя"
    )


@dp.message_created(Command("bytes"))
async def on_bytes(event: MessageCreated) -> None:
    """Скачать вложение из reply-сообщения в bytes."""

    url = await _answer_reply_required(event)
    if url is None:
        return

    try:
        data = await bot.download_bytes(url)
    except Exception as exc:
        logger.exception(exc)
        await event.message.answer("Не удалось скачать вложение в память.")
        return

    await event.message.answer(f"Скачано в bytes: {len(data)} байт.")


@dp.message_created(Command("stream"))
async def on_stream(event: MessageCreated) -> None:
    """Скачать вложение из reply-сообщения в BytesIO."""

    url = await _answer_reply_required(event)
    if url is None:
        return

    try:
        bio = await bot.download_bytes_io(url)
    except Exception as exc:
        logger.exception(exc)
        await event.message.answer("Не удалось скачать вложение в BytesIO.")
        return

    await event.message.answer(
        f"Скачано в BytesIO: {bio.name}, {len(bio.getbuffer())} байт."
    )


@dp.message_created(F.message.body.attachments)
async def on_attachment(event: MessageCreated) -> None:
    """Сохранить первое входящее вложение на диск."""

    chat_id = event.message.recipient.chat_id
    if chat_id is None:
        return

    url = _get_first_attachment_url(event)
    if url is None:
        await event.message.answer("У вложения нет URL для скачивания.")
        return

    await bot.send_action(chat_id=chat_id, action=SenderAction.SENDING_FILE)

    try:
        path = await bot.download_file(url, DOWNLOAD_DIR)
    except Exception as exc:
        logger.exception(exc)
        await event.message.answer("Не удалось скачать вложение.")
        return

    await event.message.answer(f"Файл сохранён:\n{path}")


async def main() -> None:
    """Точка входа."""

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
