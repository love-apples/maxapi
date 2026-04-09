<p align="center">
  <a href="https://github.com/love-apples/maxapi"><img src="logo.png" alt="MaxAPI"></a>
</p>


<p align="center">
<a href='https://max.ru/join/IPAok63C3vFqbWTFdutMUtjmrAkGqO56YeAN7iyDfc8'>MAX Чат</a> •
<a href='https://t.me/maxapi_github'>TG Чат</a>
</p>

<p align="center">
<a href='https://pypi.org/project/maxapi/'>
  <img src='https://img.shields.io/pypi/v/maxapi.svg' alt='PyPI version'></a>
<a href='https://pypi.org/project/maxapi/'>
  <img src='https://img.shields.io/pypi/pyversions/maxapi.svg' alt='Python Version'></a>
<a href='https://codecov.io/gh/love-apples/maxapi'>
  <img src='https://img.shields.io/codecov/c/github/love-apples/maxapi.svg' alt='Coverage'></a>
<a href='https://love-apples/maxapi/blob/main/LICENSE'>
  <img src='https://img.shields.io/github/license/love-apples/maxapi.svg' alt='License'></a>
</p>


## ● Документация и примеры использования

Можно посмотреть здесь: https://love-apples.github.io/maxapi/

## ● Установка из PyPi

Стабильная версия

```bash
pip install maxapi
```

## ● Установка из GitHub

Свежая версия, возможны баги. Рекомендуется только для ознакомления с новыми коммитами.

```bash
pip install git+https://github.com/love-apples/maxapi.git
```



## ● Быстрый старт

Если вы тестируете бота в чате - не забудьте дать ему права администратора!

### ● Запуск Polling

Если у бота установлены подписки на Webhook - события не будут приходить при методе `start_polling`. При таком случае удалите подписки на Webhook через `await bot.delete_webhook()` перед `start_polling`.

```python
import asyncio
import logging

from maxapi import Bot, Dispatcher
from maxapi.types import BotStarted, Command, MessageCreated

logging.basicConfig(level=logging.INFO)

# Внесите токен бота в переменную окружения MAX_BOT_TOKEN
# Не забудьте загрузить переменные из .env в os.environ
# или задайте его аргументом в Bot(token='...')
bot = Bot()
dp = Dispatcher()

# Ответ бота при нажатии на кнопку "Начать"
@dp.bot_started()
async def bot_started(event: BotStarted):
    await event.bot.send_message(
        chat_id=event.chat_id,
        text='Привет! Отправь мне /start'
    )

# Ответ бота на команду /start
@dp.message_created(Command('start'))
async def hello(event: MessageCreated):
    await event.message.answer("Пример чат-бота для MAX 💙")


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
```

### ● Запуск Webhook

Webhook работает «из коробки» — aiohttp уже включён в базовый пакет:

```bash
pip install maxapi
```

Указан пример простого запуска, для более низкого уровня можете рассмотреть [этот пример](https://love-apples.github.io/maxapi/examples/#_6).
```python
import asyncio
import logging

from maxapi import Bot, Dispatcher
from maxapi.types import BotStarted, Command, MessageCreated

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()


# Команда /start боту
@dp.message_created(Command('start'))
async def hello(event: MessageCreated):
    await event.message.answer("Привет из вебхука!")


async def main():
    await dp.handle_webhook(
        bot=bot,
        host='0.0.0.0',
        port=8080,
    )


if __name__ == '__main__':
    asyncio.run(main())
```

> **Хотите использовать FastAPI или Litestar вместо aiohttp?**
> Установите нужную опциональную зависимость:
> ```bash
> pip install maxapi[fastapi]   # FastAPI + uvicorn
> pip install maxapi[litestar]  # Litestar + uvicorn
> ```
>
> Пример запуска через **FastAPI**:
> ```python
> import asyncio
> import uvicorn
> from fastapi import FastAPI
> from maxapi.webhook.fastapi import FastAPIMaxWebhook
>
> async def main():
>     webhook = FastAPIMaxWebhook(dp=dp, bot=bot)
>     app = FastAPI(lifespan=webhook.lifespan)
>     webhook.setup(app, path='/webhook')
>     await uvicorn.Server(uvicorn.Config(app, host='0.0.0.0', port=8080)).serve()
>
> asyncio.run(main())
> ```
>
> Пример запуска через **Litestar**:
> ```python
> import asyncio
> import uvicorn
> from maxapi.webhook.litestar import LitestarMaxWebhook
>
> async def main():
>     webhook = LitestarMaxWebhook(dp=dp, bot=bot)
>     app = webhook.create_app(path='/webhook')
>     await uvicorn.Server(uvicorn.Config(app, host='0.0.0.0', port=8080)).serve()
>
> asyncio.run(main())
> ```

## ● Примеры ботов

> **Опциональная зависимость для примеров:** примеры поддерживают загрузку переменных окружения из `.env` файла через `python-dotenv`:
> ```bash
> pip install python-dotenv
> ```
> Без этого пакета `.env` просто не загружается, но токен можно передать напрямую:
> `MAX_BOT_TOKEN=ваш_токен python examples/01_echo_bot.py`

В директории [`examples/`](examples/) находятся готовые к запуску примеры ботов, покрывающие основные сценарии использования библиотеки. Каждый пример — самодостаточный `.py` файл с подробными комментариями на русском языке.

Запуск любого примера:
```bash
MAX_BOT_TOKEN=ваш_токен python examples/01_echo_bot.py
```

### Базовые

| Пример | Описание | Что изучите |
|--------|----------|-------------|
| [`01_echo_bot.py`](examples/01_echo_bot.py) | Эхо-бот — простейший старт | `Bot`, `Dispatcher`, `CommandStart`, `BotStarted`, `SenderAction`, polling |
| [`02_formatting_bot.py`](examples/02_formatting_bot.py) | Форматирование текста | `Bold`, `Italic`, `Code`, `Link`, `UserMention`, `Text`, `as_html()`, `TextFormat` |
| [`03_keyboard_bot.py`](examples/03_keyboard_bot.py) | Inline-клавиатуры и callbacks | `InlineKeyboardBuilder`, `CallbackButton`, `LinkButton`, `RequestContactButton`, `event.answer()`, навигация «Назад» |

### Средний уровень

| Пример | Описание | Что изучите |
|--------|----------|-------------|
| [`04_fsm_bot.py`](examples/04_fsm_bot.py) | Пошаговая форма (FSM) | `StatesGroup`, `State`, `BaseContext`, `set_state()`, `update_data()`, `clear()`, валидация ввода |
| [`05_media_bot.py`](examples/05_media_bot.py) | Работа с медиа-файлами | `InputMedia`, `InputMediaBuffer`, `upload_media()`, `forward()`, обработка вложений по типу |
| [`06_admin_bot.py`](examples/06_admin_bot.py) | Управление чатом | `pin_message()`, `delete_message()`, `edit_message()`, `get_chat_by_id()`, `user_added`, `user_removed` |

### Продвинутый уровень

| Пример | Описание | Что изучите |
|--------|----------|-------------|
| [`07_router_bot.py`](examples/07_router_bot.py) | Модульная архитектура | `Router`, `include_routers()`, `BaseFilter`, роутер-уровневые middleware и фильтры |
| [`08_middleware_bot.py`](examples/08_middleware_bot.py) | Middleware паттерны | `BaseMiddleware`, логирование, throttling, авторизация, обработка ошибок, `outer_middleware()` |
| [`09_webhook_bot.py`](examples/09_webhook_bot.py) | Webhook + FastAPI | `FastAPIMaxWebhook`, `subscribe_webhook()`, `secret`, кастомные роуты, `lifespan` |
| [`10_callback_payload_bot.py`](examples/10_callback_payload_bot.py) | Типизированные payloads | `CallbackPayload`, `prefix`, `pack()`, `filter()`, каталог с навигацией |

### Миграция с Telegram

Каждый пример содержит в заголовке аналог из экосистемы Telegram (aiogram / python-telegram-bot). Подробная таблица отличий — в [`examples/README.md`](examples/README.md#миграция-с-telegram-aiogram).

| maxapi | aiogram |
|--------|---------|
| `@dp.message_created(Command("start"))` | `@dp.message(CommandStart())` |
| `event: MessageCreated` → `event.message.body.text` | `message: Message` → `message.text` |
| `@dp.message_callback(...)` + `event.answer()` | `@dp.callback_query(...)` + `callback.answer()` |
| `BotStarted` (кнопка «Начать») | Нет аналога (только `/start`) |
| `dp.start_polling(bot)` | `dp.start_polling()` |
| `InputMedia(path="file.jpg")` | `FSInputFile("file.jpg")` |
| `CallbackPayload(prefix="...")` | `CallbackData(prefix="...")` |
