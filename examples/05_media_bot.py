"""
Медиа-бот — работа с файлами и вложениями в maxapi.

Демонстрирует:
- Отправку изображения из файла через InputMedia(path)
- Отправку из байтового буфера через InputMediaBuffer
- Предварительную загрузку через bot.upload_media()
- Обработку входящих вложений: image, file, audio, video
- Пересылку сообщений через message.forward()
- SenderAction.SENDING_PHOTO / SENDING_VIDEO / SENDING_FILE

Команды:
    /photo     — отправить тестовое изображение из файла
    /buffer    — отправить изображение из буфера (байты)
    /upload    — загрузить медиа заранее, затем отправить

Любой файл/фото/аудио/видео от пользователя пересылается обратно
с описанием типа вложения.

Аналог Telegram: send_photo, send_document, send_audio, forward_message

Запуск:
    MAX_BOT_TOKEN=your_token python 05_media_bot.py
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

# Опционально: загрузка .env, если установлен python-dotenv
with contextlib.suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv()
from maxapi import Bot, Dispatcher, F
from maxapi.enums.sender_action import SenderAction
from maxapi.filters.command import Command, CommandStart
from maxapi.types.attachments.audio import Audio
from maxapi.types.attachments.file import File
from maxapi.types.attachments.image import Image
from maxapi.types.attachments.sticker import Sticker
from maxapi.types.attachments.video import Video
from maxapi.types.input_media import InputMedia, InputMediaBuffer

if TYPE_CHECKING:
    from maxapi.types.updates.message_created import MessageCreated

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()

PHOTO_PATH = Path(__file__).resolve().parent.parent / "logo.png"


@dp.message_created(CommandStart())
async def on_start(event: MessageCreated) -> None:
    """Приветствие с описанием команд."""
    await event.message.answer(
        "Медиа-бот готов!\n\n"
        "Команды:\n"
        "/photo  — фото из файла\n"
        "/buffer — фото из буфера\n"
        "/upload — предзагрузка медиа\n\n"
        "Пришли мне любой файл, фото, аудио или видео — "
        "я расскажу, что получил, и перешлю обратно."
    )


@dp.message_created(Command("photo"))
async def cmd_photo(event: MessageCreated) -> None:
    """Отправка изображения из локального файла."""
    chat_id = event.message.recipient.chat_id
    if chat_id is None:
        return

    # Показываем индикатор «отправляет фото...»
    await bot.send_action(chat_id=chat_id, action=SenderAction.SENDING_PHOTO)

    # InputMedia принимает путь к файлу
    media = InputMedia(path=str(PHOTO_PATH))
    await event.message.answer(
        text="Фото из файла:",
        attachments=[media],
    )


@dp.message_created(Command("buffer"))
async def cmd_buffer(event: MessageCreated) -> None:
    """Отправка изображения из байтового буфера (in-memory).

    Полезно, когда файл генерируется на лету (например, captcha, график).
    """
    chat_id = event.message.recipient.chat_id
    if chat_id is None:
        return
    await bot.send_action(chat_id=chat_id, action=SenderAction.SENDING_PHOTO)

    # Читаем обычный PNG в память. В реальном проекте здесь может быть
    # результат PIL, matplotlib, reportlab и т.д.
    image_bytes = PHOTO_PATH.read_bytes()
    # InputMediaBuffer принимает bytes и имя файла
    media = InputMediaBuffer(buffer=image_bytes, filename="logo.png")
    await event.message.answer(
        text="Фото из буфера (сгенерировано в памяти):",
        attachments=[media],
    )


@dp.message_created(Command("upload"))
async def cmd_upload(event: MessageCreated) -> None:
    """Предзагрузка медиа через upload_media, затем повторная отправка.

    Паттерн полезен для рассылки одного изображения многим пользователям:
    загружаем один раз — отправляем по token'у.
    """
    chat_id = event.message.recipient.chat_id
    if chat_id is None:
        return
    await bot.send_action(chat_id=chat_id, action=SenderAction.SENDING_PHOTO)

    # Загружаем файл на серверы Max и получаем token
    uploaded = await bot.upload_media(InputMedia(path=str(PHOTO_PATH)))

    await event.message.answer(
        f"Медиа загружено! token: {uploaded.payload.token}\n"
        "Теперь его можно отправлять без повторной загрузки."
    )

    # Отправляем по полученному token
    await event.message.answer(
        text="Отправлено по upload-token:",
        attachments=[uploaded],
    )


# ── Обработка входящих вложений ────────────────────────────────────────────


@dp.message_created(F.message.body.attachments)
async def on_attachment(event: MessageCreated) -> None:
    """Получено сообщение с вложением — описываем тип и пересылаем."""
    body = event.message.body
    attachments = body.attachments if body else None
    if not attachments:
        return

    # Маппинг реальных классов вложений maxapi на человекочитаемые
    # названия и подходящий SenderAction. Используем сами классы, а не
    # строковые имена — так мы защищены от опечаток и переименований.
    first = attachments[0]
    if isinstance(first, Image):
        label, action = "фотографию", SenderAction.SENDING_PHOTO
    elif isinstance(first, Video):
        label, action = "видео", SenderAction.SENDING_VIDEO
    elif isinstance(first, Audio):
        label, action = "аудио", SenderAction.SENDING_AUDIO
    elif isinstance(first, File):
        label, action = "файл", SenderAction.SENDING_FILE
    elif isinstance(first, Sticker):
        label, action = "стикер", SenderAction.SENDING_FILE
    else:
        label, action = "вложение", SenderAction.SENDING_FILE

    chat_id = event.message.recipient.chat_id
    if chat_id is None:
        return
    await bot.send_action(chat_id=chat_id, action=action)

    # Информируем пользователя о полученном вложении
    count = len(attachments)
    await event.message.answer(
        f"Получено {count} вложение(й), тип: {label}. Пересылаю..."
    )

    # Пересылаем оригинальное сообщение обратно
    await event.message.forward(chat_id=chat_id)


async def main() -> None:
    """Точка входа."""
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
