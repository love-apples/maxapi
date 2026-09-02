# Получение метаинформации о медиафайлах

Библиотека `maxapi` позволяет извлекать метаданные медиафайлов (формат, размеры, длительность, битрейт) по URL **без полной загрузки**.
Используется библиотека `url-media-probe` (`MediaProbe` / `MediaInfo`).

Это полезно для:

- Быстрой проверки типа файла перед скачиванием.
- Получения размеров изображений/видео для отображения в UI.
- Определения длительности аудио/видео для превью.

## Поддерживаемые форматы

`MediaProbe` распознает метаданные для популярных медиаформатов:
* Изображения: JPEG, PNG, GIF, WebP (VP8/VP8L/VP8X)
* Видео: MP4/MOV, AVI, MKV, WEBM, OGV
* Аудио: MP3, AAC, WAV, WMA, FLAC, OGG, M4A

Для каждого формата извлекаются поля (если доступно):
width, height, duration, fps, sample_rate, bitrate_nominal, bitrate_avg

## Быстрый старт: `UrlStr.get_info()`

Самый простой способ — получить URL вложения и вызвать `get_info()`:

```python
# url — это UrlStr из поля attachment.url
info = await url.get_info()

print(info)

# Или отдельно по интересующим полям
print(f"Формат: {info.format}")
print(f"Размеры: {info.width}x{info.height}")
print(f"Длительность: {info.duration} сек")
print(f"Статус: {info.status}")  # ok, partial или error
if info.status != "ok":
    print(f"  Комментарий парсера: {info.parse_note}")
```

## Сохранение файла на диск

После `get_info()` можно сохранить файл целиком, используя уже скачанные данные и активное соединение:

```python
path = await url.download_file("/tmp/downloads")
print(f"Сохранено: {path}")
```

Метод можно вызывать и без предварительного `get_info()`:

```python
path = await url.download_file("/tmp/downloads")  # без get_info()
```

## `url.download_file()` или `bot.download_file()`?

Оба метода сохраняют файл на диск, оба поддерживают ретраи сети
(обрывы соединения и статусы 429/5xx) и выбрасывают одинаковое
исключение `DownloadFileError`. Различие — в источнике URL
и работе с метаданными:

| | `url.download_file(dir)` | `bot.download_file(url, dir)` |
|---|---|---|
| Вызов | прямо на URL из вложения (`UrlStr`) | по любой строке-URL |
| Метаданные | можно сначала оценить файл через `get_info()`, тогда скачивание переиспользует уже установленный пробник и соединение без разрыва | не определяет |
| Байты без сохранения в файл | — | bot.download_bytes(url) и bot.download_bytes_io(url) |

Для вложений из сообщений удобнее `url.download_file()`,
для произвольных ссылок — `bot.download_file()`.

Комбинированный сценарий — сначала посмотреть метаданные url.get_info(), затем
выбрать способ скачивания по размеру: большие файлы — на диск, маленькие —
в память:

```python
info = await url.get_info(max_total=0)  # Только размер файла, без медиапробы
if info.status == "ok" and (info.file_size or 0) > 50 * 1024 * 1024:
    path = await url.download_file("/tmp/downloads")
    # Работа с файлом
else:
    file_bytes = await bot.download_bytes(url)
    # Работа с байтами
```

## Обработка статусов

Метод возвращает `MediaInfo` со статусом:
* `ok` — все ключевые метаданные успешно извлечены.
* `partial` — часть данных получена, но чего-то не хватает (например, длительность для MP4 с moov в конце файла).
* `error` — произошла ошибка (сеть, HTML-страница вместо файла) и не удалось определить даже размер файла.

```python
info = await url.get_info()

if info.status == "ok":
    print(f"Полные метаданные: {info.format}, {info.width}x{info.height}")
elif info.status == "partial":
    print(f"Частичные данные: {info.format}, примечание: {info.parse_note}")
else:
    print(f"Ошибка: {info.parse_note}")
```

## Как это работает?

`MediaProbe` (внутри `UrlStr.get_info()`) использует частичную загрузку:
* GET-запрос и чтение первых N байт для получения Content-Type/Content-Length и сигнатуры файла.
* Скачивание хвоста 64 КБ — для форматов, где метаданные в конце (MP4 с moov в конце,
  OGG с длительностью в последней грануле).
* Чтение начала файла от 4 до 256 КБ в зависимости от формата.

Если сервер не поддерживает Range-запросы, `MediaProbe` адаптируется и работает с тем, что есть,
возвращая статус partial при невозможности определить некоторые поля.

## Пример в боте: команда /info

Добавим команду, которая показывает метаинформацию о файле из reply-сообщения:

```python
import asyncio

from maxapi import Bot, Dispatcher
from maxapi.filters.command import Command
from maxapi.types import MessageCreated

bot = Bot(token="ваш_токен")
dp = Dispatcher()


@dp.message_created(Command("info"))
async def cmd_info(event: MessageCreated):
    replied_body = event.message.link.message if event.message.link else None
    if not replied_body or not replied_body.attachments:
        await event.message.answer(
            "ℹ️ Ответьте этой командой на сообщение с файлом."
        )
        return

    for att in replied_body.attachments:
        if hasattr(att, "url"):
            info = await att.url.get_info()
            if info.status == "ok":
                await event.message.answer(str(info))
                return

    await event.message.answer("Вложение не найдено")


if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
```

Более подробный пример [05_media_bot.py](https://github.com/love-apples/maxapi/blob/main/examples/05_media_bot.py)
