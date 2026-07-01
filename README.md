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
  <img src="https://static.pepy.tech/badge/maxapi/month" alt="PyPI downloads per month">
<a href='https://pypi.org/project/maxapi/'>
  <img src='https://img.shields.io/pypi/pyversions/maxapi.svg' alt='Python Version'></a>
<a href='https://codecov.io/gh/love-apples/maxapi'>
  <img src='https://img.shields.io/codecov/c/github/love-apples/maxapi.svg' alt='Coverage'></a>
<a href='https://github.com/love-apples/maxapi/actions/workflows/tests.yml'>
  <img src='https://github.com/love-apples/maxapi/actions/workflows/tests.yml/badge.svg' alt='Tests'></a>
<a href='https://github.com/love-apples/maxapi/actions/workflows/lint.yml'>
  <img src='https://github.com/love-apples/maxapi/actions/workflows/lint.yml/badge.svg' alt='Ruff'></a>
<a href='https://github.com/love-apples/maxapi/actions/workflows/docs.yml'>
  <img src='https://github.com/love-apples/maxapi/actions/workflows/docs.yml/badge.svg' alt='Docs'></a>
<a href='https://github.com/love-apples/maxapi/blob/main/LICENSE'>
  <img src='https://img.shields.io/github/license/love-apples/maxapi.svg' alt='License'></a>
</p>


## Документация и ссылки

- Документация maxapi: https://love-apples.github.io/maxapi/
- Официальная документация MAX Bot API: https://dev.max.ru/docs-api/
- Примеры ботов: https://love-apples.github.io/maxapi/examples/

## Возможности

- Асинхронный `Bot` с тонкими обёртками над методами MAX Bot API.
- `Dispatcher`, `Router`, фильтры, `F` и middleware в стиле aiogram.
- FSM-контекст через `MemoryContext` и `RedisContext`.
- Polling и webhook через aiohttp, FastAPI или Litestar.
- Работа с медиа: загрузка, отправка и скачивание файлов.
- Inline-кнопки, callbacks и типизированные callback payloads.

## Установка из PyPI

Стабильная версия

```bash
pip install maxapi
```

Если проект управляется через uv:

```bash
uv add maxapi
```

## Установка из GitHub

Свежая версия, возможны баги. Рекомендуется только для ознакомления с новыми коммитами.

```bash
pip install git+https://github.com/love-apples/maxapi.git
```


## Быстрый старт

Если вы тестируете бота в чате - не забудьте дать ему права администратора!

### Запуск Polling

> ⚠️ Long Polling ограничен по скорости и сроку хранения событий и **не
> подходит для production-окружения**. Для боевого окружения используйте
> [Webhook](#запуск-webhook).

Если у бота есть активные Webhook-подписки, события не будут приходить
через `start_polling`. Перед переходом на polling удалите подписки через
`await bot.delete_webhook()`.

```python
import asyncio
import logging

from maxapi import Bot, Dispatcher, F
from maxapi.filters.command import CommandStart
from maxapi.types import BotStarted, MessageCreated

logging.basicConfig(level=logging.INFO)

# Внесите токен бота в переменную окружения MAX_BOT_TOKEN
# Не забудьте загрузить переменные из .env в os.environ
# или задайте его аргументом в Bot(token='...')
bot = Bot()
dp = Dispatcher()

# Ответ бота при нажатии на кнопку "Начать"
@dp.bot_started()
async def bot_started(event: BotStarted):
    await bot.send_message(
        chat_id=event.chat_id,
        text='Привет! Отправь мне /start'
    )

# Ответ бота на команду /start
@dp.message_created(CommandStart())
async def hello(event: MessageCreated):
    await event.message.answer("Пример чат-бота для MAX 💙")


@dp.message_created(F.message.body.text)
async def echo(event: MessageCreated):
    await event.message.answer(event.message.body.text)


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
```

### Запуск Webhook

> 🔒 С 25.05.2026 прекращается поддержка получения вебхуков по HTTP и
> самоподписных сертификатов. Используйте **HTTPS** и сертификаты, выданные
> доверенным центром сертификации.

Webhook работает «из коробки» — aiohttp уже включён в базовый пакет:

```bash
pip install maxapi
```

Для проекта на uv:

```bash
uv add maxapi
```

Ниже простой запуск через aiohttp. Для production-интеграции с FastAPI,
подпиской webhook и проверкой `secret` смотрите
[пример 09_webhook_bot.py](examples/09_webhook_bot.py).

```python
import asyncio
import logging

from maxapi import Bot, Dispatcher
from maxapi.filters.command import CommandStart
from maxapi.types import MessageCreated

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()


# Команда /start боту
@dp.message_created(CommandStart())
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

#### FastAPI и Litestar

Если хотите использовать FastAPI или Litestar вместо aiohttp, установите
нужную опциональную зависимость через pip:

```bash
pip install "maxapi[fastapi]"
pip install "maxapi[litestar]"
```

Или через uv:

```bash
uv add "maxapi[fastapi]"
uv add "maxapi[litestar]"
```

Пример запуска через **FastAPI**:

```python
import asyncio
import uvicorn
from fastapi import FastAPI
from maxapi.webhook.fastapi import FastAPIMaxWebhook

async def main():
    webhook = FastAPIMaxWebhook(dp=dp, bot=bot)
    app = FastAPI(lifespan=webhook.lifespan)
    webhook.setup(app, path='/webhook')
    await uvicorn.Server(uvicorn.Config(app, host='0.0.0.0', port=8080)).serve()

asyncio.run(main())
```

Пример запуска через **Litestar**:

```python
import asyncio
import uvicorn
from maxapi.webhook.litestar import LitestarMaxWebhook

async def main():
    webhook = LitestarMaxWebhook(dp=dp, bot=bot)
    app = webhook.create_app(path='/webhook')
    await uvicorn.Server(uvicorn.Config(app, host='0.0.0.0', port=8080)).serve()

asyncio.run(main())
```
