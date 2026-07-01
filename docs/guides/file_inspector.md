# Получение метаинформации о медиафайлах

Библиотека `maxapi` позволяет извлекать метаданные медиафайлов (формат, размеры, длительность, битрейт) по URL **без полной загрузки**, локальному пути или байтам в памяти.
Анализирует сигнатуры и заголовки в первых и последних байтах файла. Скачивает минимум данных, докачивает
только если не хватило.

Это полезно для:

- Быстрой проверки типа файла перед скачиванием.
- Получения размеров изображений/видео для отображения в UI.
- Определения длительности аудио/видео для превью.

## Поддерживаемые форматы

FileInspector распознает метаданные для популярных медиаформатов:
* Изображения: JPEG, PNG, GIF, WebP (VP8/VP8L/VP8X)
* Видео: MP4/MOV, AVI, MKV, WEBM, OGV
* Аудио: MP3, AAC, WAV, WMA, FLAC, OGG, M4A

Для каждого формата извлекаются поля (если доступно):
width, height, duration, fps, sample_rate, bitrate

## Быстрый старт: `bot.get_file_info()`

Самый простой способ — использовать метод `bot.get_file_info()`, который принимает URL файла и возвращает `FileInfo`:

```python
from maxapi import Bot

bot = Bot(token="YOUR_TOKEN")

# Получаем метаинформацию о файле по URL
info = await bot.get_file_info(
    "https://example.com/video.mp4",
    timeout=10,  # таймаут в секундах (опционально)
)

print(info)

# Или отдельно по интересующим полям
print(f"Формат: {info.format}")
print(f"Размеры: {info.width}x{info.height}")
print(f"Длительность: {info.duration} сек")
print(f"Статус: {info.status}")  # ok, partial или error
if info.status != "ok":
    print(f"  Комментарий парсера: {info.parse_note}")
```

## Анализ файла на диске или байт в памяти

```python
from maxapi.utils import FileInspector
inspector = FileInspector()
file_info = await inspector.inspect_file("/path/to/video.avi")
file_info = await inspector.inspect_bytes(downloaded_bytes)
# Следующий метод интегрирован в bot.get_file_info(url)
file_info = await inspector.inspect_url("https://example.com/photo.jpg")
```

FileInspector можно использовать повторно для других файлов.
При этом он помнит последние скачанные данные и последний FileInfo:

```python
if inspector.last_file_info:
    print(inspector.last_file_info)
    print("Скачано начало файла", len(inspector.last_head), "байт")
    if inspector.last_tail:
        print("Скачано конца файла", len(inspector.last_tail), "байт")
```

## Обработка статусов

Метод возвращает FileInfo со статусом:
* `ok` — все ключевые метаданные успешно извлечены.
* `partial` — часть данных получена, но чего-то не хватает (например, длительность для MP4 с moov в конце файла).
* `error` — произошла ошибка (сеть, HTML-страница вместо файла) и не удалось определить даже размер файла.

```python
info = await bot.get_file_info(url)

if info.status == "ok":
    print(f"Полные метаданные: {info.format}, {info.width}x{info.height}")
elif info.status == "partial":
    print(f"Частичные данные: {info.format}, примечание: {info.parse_note}")
else:
    print(f"Ошибка: {info.parse_note}")
```

## Как это работает?

FileInspector использует частичную загрузку:
* HEAD-запрос для получения Content-Type и Content-Length.
* Скачивание хвоста 64 КБ — для форматов, где метаданные в конце (MP4 с moov в конце,
  OGG с длительностью в последней грануле).
* Чтение начала файла от 4 до 256 КБ в зависимости от формата.

Если сервер не поддерживает Range-запросы, FileInspector адаптируется и работает с тем, что есть,
возвращая статус partial при невозможности определить некоторые поля.

## Безопасность и авторизация

Если вы передаете aiohttp.ClientSession с заголовками авторизации (Authorization, Cookie), они не будут отправлены на сторонние домены по умолчанию. Это защита от утечки токенов.
Чтобы разрешить отправку авторизации на внешний URL:

```python
from maxapi.utils import FileInspector
inspector = FileInspector()
info = await inspector.inspect_url(
    "https://external.com/private.mp4",
    session=session_with_auth,
    allow_external_auth=True,  # явно разрешаем
)
```

Доверенные домены (**oneme.ru**, **okcdn.ru**) всегда принимают авторизацию без этого флага.

## Пример в боте: команда /info

Добавим команду, которая показывает метаинформацию о файле из reply-сообщения:

```python
import asyncio
from maxapi import Bot, Dispatcher
from maxapi.types import Message

bot = Bot(token="ваш_токен")
dp = Dispatcher()

@dp.message_created(commands=["info"])
async def cmd_info(event: MessageCreated):
    replied_body = event.message.link.message if event.message.link else None
    if not replied_body or not replied_body.attachments:
        await event.message.answer("ℹ️ Ответьте этой командой на сообщение с файлом.")
        return

    first_url = None
    # Получаем URL вложений до первого успеха
    if replied_body.attachments:
        for att in replied_body.attachments:
            if hasattr(att, "url"):
                file_info = await bot.get_file_info(att.url)
                if file_info.status == "ok":
                    # Собрать отдельные интересующие поля
                    # text = f"Формат: {file_info.format}\n"
                    # if file_info.width and file_info.height:
                    #     text += f"Размеры: {file_info.width}x{file_info.height}\n"
                    # if file_info.duration:
                    #     text += f"Длительность: {file_info.duration} сек\n"
                    # if file_info.sample_rate:
                    #     text += f"Частота сэмплов: {file_info.sample_rate} Гц\n"
                    # text += f"Статус: {file_info.status}"
                    # Или просто:
                    text = str(file_info)
                    await event.message.answer(text)
                    return

    await event.message.answer("Вложение не найдено")
    return


if __name__ == '__main__':
    asyncio.run(dp.start_polling(bot))
```

Более подробный пример (05_media_bot.py)[https://github.com/love-apples/maxapi/blob/main/examples/05_media_bot.py]
