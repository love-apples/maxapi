"""
Медиа-бот — работа с файлами и вложениями в maxapi.

Демонстрирует:
- Отправку изображения из файла через InputMedia(path)
- Отправку из байтового буфера через InputMediaBuffer
- Предварительную загрузку через bot.upload_media()
- SenderAction.SENDING_PHOTO / SENDING_VIDEO / SENDING_FILE

Аналог Telegram: send_photo, send_document, send_audio

Запуск:
    MAX_BOT_TOKEN=your_token python 05_media_bot.py
"""

import base64
import contextlib
import logging
import os
import tempfile

# Опционально: загрузка .env, если установлен python-dotenv
with contextlib.suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv()
from maxapi import Bot
from maxapi.enums.sender_action import SenderAction
from maxapi.types.input_media import InputMedia, InputMediaBuffer

logging.basicConfig(level=logging.INFO)

bot = Bot()

# Минимальный валидный PNG 1x1 пиксель (красный) — fallback,
# чтобы пример запускался без ручного добавления sample.jpg.
_PNG_1X1_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
    "2mP8/58BAwAI/AL+hc2rNAAAAABJRU5ErkJggg=="
)


def get_sample_image_path() -> str:
    """Возвращает путь к тестовому изображению.

    Если рядом со скриптом есть sample.jpg — используем его, иначе
    создаём временный PNG 1x1 (красный пиксель). Так пример работает
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


def main() -> None:
    """Демонстрация работы с медиа через Bot API."""
    # В реальном боте chat_id берётся из входящего обновления (update),
    # здесь для демонстрации читаем из переменной окружения.
    user_id = os.environ.get("MAX_USER_ID")
    if user_id is None:
        print(
            "Установите MAX_USER_ID для демонстрации отправки.\n"
            "Пример: MAX_USER_ID=12345 MAX_BOT_TOKEN=your_token python 05_media_bot.py"
        )
        return

    uid = int(user_id)

    # ── 1. Отправка изображения из локального файла ──────────────────────
    print("Отправка фото из файла...")
    bot.send_action(chat_id=uid, action=SenderAction.SENDING_PHOTO)

    sample_path = get_sample_image_path()
    media = InputMedia(path=sample_path)
    bot.send_message(
        user_id=uid,
        text="Фото из файла:",
        attachments=[media],
    )

    # ── 2. Отправка изображения из байтового буфера (in-memory) ──────────
    print("Отправка фото из буфера...")
    bot.send_action(chat_id=uid, action=SenderAction.SENDING_PHOTO)

    png_1x1 = base64.b64decode(_PNG_1X1_B64)
    buffer_media = InputMediaBuffer(buffer=png_1x1, filename="generated.png")
    bot.send_message(
        user_id=uid,
        text="Фото из буфера (сгенерировано в памяти):",
        attachments=[buffer_media],
    )

    # ── 3. Предзагрузка медиа через upload_media ─────────────────────────
    print("Предзагрузка медиа...")
    bot.send_action(chat_id=uid, action=SenderAction.SENDING_PHOTO)

    uploaded = bot.upload_media(InputMedia(path=sample_path))

    bot.send_message(
        user_id=uid,
        text=f"Медиа загружено! token: {uploaded.payload.token}\n"
        "Теперь его можно отправлять без повторной загрузки.",
    )

    # Отправляем по полученному token
    bot.send_message(
        user_id=uid,
        text="Отправлено по upload-token:",
        attachments=[uploaded],
    )

    print("Готово!")


if __name__ == "__main__":
    main()
