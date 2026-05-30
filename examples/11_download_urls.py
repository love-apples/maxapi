"""
Медиа-архив бот — три метода загрузки файлов.

Демонстрирует:
- bot.download_bytes()    — загрузка в память для Pillow
- bot.download_bytes_io() — потоковое чтение (ZIP)
- bot.download_file()     — сохранение в архив

Установите Pillow:
    pip install Pillow

Логика:
- Фото → размытие и отправка обратно (download_bytes)
- Всё остальное → сохранить в архив (download_file)
- /archive — прислать ZIP со всеми файлами архива
- /zipinfo ответом на архив — содержимое ZIP (download_bytes_io)

Запуск:
    MAX_BOT_TOKEN=your_token python 11_download_bytes.py
"""

import asyncio
import contextlib
import io
import logging
import zipfile
from pathlib import Path

with contextlib.suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv()

import PIL
from maxapi import Bot, Dispatcher, F
from maxapi.enums.sender_action import SenderAction
from maxapi.filters.command import Command, CommandStart
from maxapi.types.attachments.image import Image
from maxapi.types.input_media import InputMediaBuffer
from maxapi.types.updates.message_created import MessageCreated

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()

ARCHIVE_DIR = Path("media_archive")


# ============================================================================
# Хелперы
# ============================================================================


def _get_first_attachment_url(attachments) -> str | None:
    """Извлекает URL из первого вложения."""
    if not attachments:
        return None
    first = attachments[0]
    if hasattr(first, "url") and first.url:
        return first.url
    return None


def _archive_size() -> str:
    """Размер медиа-архива."""
    if not ARCHIVE_DIR.exists():
        return "0 байт"
    total = sum(
        f.stat().st_size for f in ARCHIVE_DIR.rglob("*") if f.is_file()
    )
    for unit in ("байт", "КБ", "МБ", "ГБ"):
        if total < 1024:
            return f"{total} {unit}"
        total //= 1024
    return f"{total} ГБ"


# ============================================================================
# Команды
# ============================================================================


@dp.message_created(CommandStart())
async def on_start(event: MessageCreated) -> None:
    await event.message.answer(
        "Медиа-архив бот готов!"
        "\n\nПришли мне:"
        "\n📷 Фото — размою и отправлю обратно"
        "\n📎 Всё остальное — сохраню в архив"
        "\n\nКоманды:"
        "\n/archive — прислать ZIP со всеми файлами архива"
        "\n/zipinfo ответом на архив — содержимое ZIP"
        f"\n\nРазмер архива: {_archive_size()}"
    )


@dp.message_created(Command("archive"))
async def cmd_archive(event: MessageCreated) -> None:
    """Отправляет ZIP-архив со всеми файлами медиа-архива."""
    chat_id = event.message.recipient.chat_id
    if chat_id is None:
        return

    if not ARCHIVE_DIR.exists() or not list(ARCHIVE_DIR.rglob("*")):
        await event.message.answer("Архив пуст.")
        return

    await bot.send_action(chat_id=chat_id, action=SenderAction.SENDING_FILE)

    # Создаём ZIP в памяти
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in ARCHIVE_DIR.rglob("*"):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(ARCHIVE_DIR))
    output.seek(0)

    media = InputMediaBuffer(
        buffer=output.read(), filename="media_archive.zip"
    )
    await event.message.answer(
        text=f"Архив всех файлов готов!\nРазмер архива: {_archive_size()}",
        attachments=[media],
    )


# ============================================================================
# Обработка вложений
# ============================================================================


@dp.message_created(F.message.body.attachments)
async def on_attachment(event: MessageCreated) -> None:
    """Обрабатывает вложение: фото — blur, остальное — в архив."""
    body = event.message.body
    attachments = body.attachments if body else None
    if not attachments:
        return

    chat_id = event.message.recipient.chat_id
    if chat_id is None:
        return

    url = _get_first_attachment_url(attachments)
    if not url:
        return

    if isinstance(attachments[0], Image):
        await _handle_photo(event, url)
    else:
        await _handle_save(event, url)


@dp.message_created(Command("zipinfo"))
async def cmd_zipinfo(event: MessageCreated) -> None:
    """Показывает содержимое ZIP-архива — download_bytes_io()."""
    chat_id = event.message.recipient.chat_id
    if chat_id is None:
        return

    link = event.message.link
    replied_body = link.message if link else None
    if not replied_body or not replied_body.attachments:
        await event.message.answer(
            "ℹ️ Ответьте этой командой на сообщение с ZIP-архивом."
        )
        return

    url = _get_first_attachment_url(replied_body.attachments)
    if not url:
        await event.message.answer("⚠️ Не удалось получить URL вложения.")
        return

    await bot.send_action(chat_id=chat_id, action=SenderAction.SENDING_FILE)

    try:
        # Для библиотек, которым нужны file-like объекты используем
        # download_bytes_io
        # Это минимизирует создание копий данных в памяти
        file_io = await bot.download_bytes_io(url)

        with zipfile.ZipFile(file_io) as zf:
            items = zf.namelist()
            lines = [f"📦 {file_io.name} — {len(items)} файлов:"]
            for item in items[:20]:
                info = zf.getinfo(item)
                lines.append(f"  {item} ({info.file_size} байт)")
            if len(items) > 20:
                lines.append(f"  ... и ещё {len(items) - 20}")

        await event.message.answer("\n".join(lines))
    except zipfile.BadZipFile:
        await event.message.answer("⚠️ Файл не является ZIP-архивом.")
    except Exception as e:
        log.exception("Ошибка zipinfo: %s", e)
        await event.message.answer(f"⚠️ Ошибка: {e}")


async def _handle_photo(event: MessageCreated, url: str) -> None:
    """Размытие фото — download_bytes() + Pillow."""
    chat_id = event.message.recipient.chat_id
    await bot.send_action(chat_id=chat_id, action=SenderAction.SENDING_PHOTO)

    try:
        # Скачиваем в память, получаем байты
        image_bytes = await bot.download_bytes(url)
        img = PIL.Image.open(io.BytesIO(image_bytes))
        img = img.filter(PIL.ImageFilter.GaussianBlur(radius=5))

        output = io.BytesIO()
        img.save(output, format="PNG")
        output.seek(0)

        media = InputMediaBuffer(buffer=output.read(), filename="blurred.png")
        await event.message.answer(
            text="Готово — размытие применено!",
            attachments=[media],
        )
    except Exception as e:
        log.exception("Ошибка blur: %s", e)
        await event.message.answer(f"⚠️ Ошибка: {e}")


async def _handle_save(event: MessageCreated, url: str) -> None:
    """Сохранение в архив — download_file()."""
    chat_id = event.message.recipient.chat_id
    await bot.send_action(chat_id=chat_id, action=SenderAction.SENDING_FILE)
    await event.message.answer("Сохраняю в архив...")

    try:
        # Скачиваем и сохраняем в файл, получаем путь к файлу pathlib.Path
        # ARCHIVE_DIR будет создан автоматически
        saved_path = await bot.download_file(url, ARCHIVE_DIR)
        await event.message.answer(
            f"Сохранено в архив:\n{saved_path}\n"
            f"Размер архива: {_archive_size()}"
        )
    except Exception as e:
        log.exception("Ошибка сохранения: %s", e)
        await event.message.answer(f"⚠️ Ошибка: {e}")


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
