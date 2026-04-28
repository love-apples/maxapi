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
import contextlib
import logging
import os
import tempfile

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
from maxapi.types.updates.message_created import MessageCreated

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()

# Минимальный валидный PNG 1×1 пиксель (красный) — fallback для /photo
# и /upload, чтобы пример запускался без ручного добавления sample.jpg.
_PNG_1X1_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
    "2mP8/58BAwAI/AL+hc2rNAAAAABJRU5ErkJggg=="
)


def get_sample_image_path() -> str:
    """Возвращает путь к тестовому изображению.

    Если рядом со скриптом есть sample.jpg — используем его, иначе
    создаём временный PNG 1×1 (красный пиксель). Так пример работает
    из коробки без необходимости добавлять медиа вручную.
    """
    local = os.path.join(os.path.dirname(__file__), "sample.jpg")
    if os.path.exists(local):
        return local

    tmp_path = os.path.join(tempfile.gettempdir(), "maxapi_example_sample.png")
    if not os.path.exists(tmp_path):
        with open(tmp_path, "wb") as f:
            f.write(base64.b64decode(_PNG_1X1_B64))
    return tmp_path


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

    # Берём sample.jpg, если он есть рядом со скриптом, иначе — сгенерим
    # на лету маленький PNG, чтобы пример работал «из коробки».
    sample_path = get_sample_image_path()

    # InputMedia принимает путь к файлу
    media = InputMedia(path=sample_path)
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
    if chat_id is None:
        return
    await bot.send_action(chat_id=chat_id, action=SenderAction.SENDING_PHOTO)

    # Используем тот же минимальный PNG 1×1 пиксель для демонстрации.
    # В реальном проекте здесь будет PIL, matplotlib, reportlab и т.д.
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
    if chat_id is None:
        return
    await bot.send_action(chat_id=chat_id, action=SenderAction.SENDING_PHOTO)

    sample_path = get_sample_image_path()

    # Загружаем файл на серверы Max и получаем token
    uploaded = await bot.upload_media(InputMedia(path=sample_path))

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

    # Маппинг реальных классов вложений maxapi на человекочитаемые
    # названия и подходящий SenderAction. Используем сами классы, а не
    # строковые имена — так мы защищены от опечаток и переименований.
    first = attachments[0]
    if isinstance(first, Image):
        label, action = "фотографию", SenderAction.SENDING_PHOTO
    elif isinstance(first, Video):
        label, action = "видео", SenderAction.SENDING_VIDEO
    elif isinstance(first, Audio):
        label, action = "аудио", SenderAction.SENDING_FILE
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
