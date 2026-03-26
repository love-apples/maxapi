# Документация библиотеки maxapi

**MaxAPI** — современная асинхронная Python-библиотека для разработки чат-ботов с помощью API мессенджера MAX.

Библиотека предоставляет удобный и типобезопасный интерфейс для работы с API MAX, поддерживает асинхронную работу, гибкую систему фильтров, middleware, роутеры и множество других возможностей для создания мощных чат-ботов.

## Быстрый старт

Установите библиотеку через pip:

```bash
pip install maxapi
```

> **Примечание про Webhook:** сервер на `aiohttp` уже включён в базовый пакет — дополнительных зависимостей не нужно.
> Если хотите использовать **FastAPI** или **Litestar** вместо aiohttp:
> ```bash
> pip install maxapi[fastapi]   # FastAPI + uvicorn
> pip install maxapi[litestar]  # Litestar + uvicorn
> ```

### Простой пример

Создайте простого эхо-бота, который отвечает на команду `/start`:

```python
import asyncio
import logging

from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated, Command

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
# Токен можно задать через переменную окружения MAX_BOT_TOKEN
# или передать напрямую: Bot(token='ваш_токен')
bot = Bot()
dp = Dispatcher()

# Обработчик команды /start
@dp.message_created(Command('start'))
async def start_handler(event: MessageCreated):
    await event.message.answer("Привет! 👋\nЯ простой бот на MaxAPI.")

# Обработчик всех текстовых сообщений
@dp.message_created()
async def echo_handler(event: MessageCreated):
    if event.message.body.text:
        await event.message.answer(f"Вы написали: {event.message.body.text}")

async def main():
    # Запуск бота в режиме polling
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
```

!!! warning "Важно"
    Если вы тестируете бота в чате, не забудьте дать ему права администратора!
    
    Если у бота установлены подписки на Webhook, события не будут приходить при методе `start_polling`. 
    Удалите подписки через `await bot.delete_webhook()` перед `start_polling`.

### Пример с фильтрами

Использование MagicFilter для более гибкой фильтрации:

```python
from maxapi import Bot, Dispatcher, F
from maxapi.types import MessageCreated

bot = Bot()
dp = Dispatcher()

# Обработчик только текстовых сообщений
@dp.message_created(F.message.body.text)
async def text_handler(event: MessageCreated):
    text = event.message.body.text
    await event.message.answer(f"Длина вашего сообщения: {len(text)} символов")

# Обработчик сообщений с вложениями
@dp.message_created(F.message.attachments)
async def attachment_handler(event: MessageCreated):
    await event.message.answer("Вы отправили вложение!")
```

## Лицензия

См. файл [LICENSE](https://github.com/love-apples/maxapi/blob/main/LICENSE) для подробной информации.
