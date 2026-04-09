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

import asyncio
import base64
import logging
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from maxapi import Bot, Dispatcher, F
from maxapi.enums.sender_action import SenderAction
from maxapi.filters.command import Command, CommandStart
from maxapi.types.input_media import InputMedia, InputMediaBuffer
from maxapi.types.updates.message_created import MessageCreated

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()

# Путь к тестовому изображению (должен существовать или замените на свой)
SAMPLE_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "sample.jpg")


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

    if not os.path.exists(SAMPLE_IMAGE_PATH):
        await event.message.answer(
            f"Файл sample.jpg не найден рядом со скриптом.\n"
            f"Ожидался путь: {SAMPLE_IMAGE_PATH}"
        )
        return

    # InputMedia принимает путь к файлу
    media = InputMedia(path=SAMPLE_IMAGE_PATH)
    await bot.send_message(
        chat_id=chat_id,
        text="Фото из файла:",
        attachments=[media],
    )


@dp.message_created(Command("buffer"))
async def cmd_buffer(event: MessageCreated) -> None:
    """Отправка изображения из байтового буфера (in-memory).

    Полезно, когда файл генерируется на лету (например, captcha, график).
    """
    chat_id = event.message.recipient.chat_id
    await bot.send_action(chat_id=chat_id, action=SenderAction.SENDING_PHOTO)

    # Минимальный PNG 1×1 пиксель (красный) для демонстрации
    # В реальном проекте здесь будет PIL, matplotlib, reportlab и т.д.
    _PNG_1X1_B64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
        "2mP8/58BAwAI/AL+hc2rNAAAAABJRU5ErkJggg=="
    )
    png_1x1 = base64.b64decode(_PNG_1X1_B64)
    # InputMediaBuffer принимает bytes и имя файла
    media = InputMediaBuffer(buffer=png_1x1, filename="generated.png")
    await bot.send_message(
        chat_id=chat_id,
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
    await bot.send_action(chat_id=chat_id, action=SenderAction.SENDING_PHOTO)

    if not os.path.exists(SAMPLE_IMAGE_PATH):
        await event.message.answer(
            "Файл sample.jpg не найден — предзагрузка невозможна."
        )
        return

    # Загружаем файл на серверы Max и получаем token
    uploaded = await bot.upload_media(InputMedia(path=SAMPLE_IMAGE_PATH))

    await event.message.answer(
        f"Медиа загружено! token: {uploaded.payload.token}\n"
        "Теперь его можно отправлять без повторной загрузки."
    )

    # Отправляем по полученному token
    await bot.send_message(
        chat_id=chat_id,
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

    # Определяем тип первого вложения
    first = attachments[0]
    attachment_type = type(first).__name__

    # Маппинг типов на читаемые русские названия и SenderAction
    type_map = {
        "PhotoAttachment": ("фотографию", SenderAction.SENDING_PHOTO),
        "VideoAttachment": ("видео", SenderAction.SENDING_VIDEO),
        "AudioAttachment": ("аудио", SenderAction.SENDING_FILE),
        "FileAttachment": ("файл", SenderAction.SENDING_FILE),
    }
    label, action = type_map.get(
        attachment_type, ("вложение", SenderAction.SENDING_FILE)
    )

    chat_id = event.message.recipient.chat_id
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
