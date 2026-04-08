# Примеры ботов на maxapi

Готовые к запуску примеры ботов для [MAX Messenger](https://max.ru) — российского мессенджера с открытым Bot API. Если вы писали ботов для Telegram (aiogram, python-telegram-bot) — здесь всё знакомо, но с нюансами. Примеры покажут как.

> Впервые работаете с MAX-ботами? Начните с примера 01 и двигайтесь по порядку.

## Полезные ссылки

- [MAX Messenger](https://max.ru) — скачать мессенджер
- [Документация Bot API](https://dev.max.ru/docs-api/) — официальная спецификация API
- [Документация maxapi](https://love-apples.github.io/maxapi/) — гайды и справочник библиотеки
- [MAX Чат разработчиков](https://max.ru/join/IPAok63C3vFqbWTFdutMUtjmrAkGqO56YeAN7iyDfc8) — поддержка сообщества

## Подготовка окружения

### 1. Установка

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

pip install maxapi
```

Для примера с webhook (09):
```bash
pip install maxapi[fastapi]
```

### 2. Получение токена

1. Установите [MAX Messenger](https://max.ru)
2. Найдите бота [@MasterBot](https://max.ru/masterbot) и напишите ему
3. Создайте нового бота — получите токен вида `abc123...`

### 3. Настройка токена

**Вариант A** — через переменную окружения (рекомендуется):
```bash
export MAX_BOT_TOKEN="ваш_токен"
python examples/01_echo_bot.py
```

**Вариант B** — через `.env` файл:
```bash
# Создайте файл .env в корне проекта
echo 'MAX_BOT_TOKEN=ваш_токен' > .env
```
Затем в коде бота перед созданием `Bot()`:
```python
from dotenv import load_dotenv
load_dotenv()  # Загружает переменные из .env в os.environ

bot = Bot()  # Автоматически берёт токен из MAX_BOT_TOKEN
```

> `Bot()` без аргументов ищет токен в переменной окружения `MAX_BOT_TOKEN`. Можно передать явно: `Bot(token="ваш_токен")`.

### 4. Запуск

```bash
python examples/01_echo_bot.py
```

> Если тестируете бота в групповом чате — дайте ему права администратора.

---

## Содержание

- [01. Эхо-бот](#01-эхо-бот--первый-бот-за-5-минут)
- [02. Форматирование текста](#02-форматирование-текста)
- [03. Inline-клавиатуры и callbacks](#03-inline-клавиатуры-и-callbacks)
- [04. FSM — пошаговая форма](#04-fsm--пошаговая-форма-регистрации)
- [05. Работа с медиа](#05-работа-с-медиа-файлами)
- [06. Администрирование чата](#06-администрирование-чата)
- [07. Роутеры](#07-модульная-архитектура-с-роутерами)
- [08. Middleware](#08-middleware-паттерны)
- [09. Webhook + FastAPI](#09-webhook-с-fastapi)
- [10. Типизированные payloads](#10-типизированные-callback-payloads--каталог-товаров)

### 01. Эхо-бот — первый бот за 5 минут

**Файл:** [`01_echo_bot.py`](01_echo_bot.py)

Самый простой бот: отвечает на `/start` приветствием, на любой текст — эхом. Отправляет индикатор «печатает...» перед ответом.

**Что изучите:**
- Создание `Bot` и `Dispatcher`
- Обработка `BotStarted` (нажатие кнопки «Начать»)
- Обработка команды через `CommandStart()`
- Фильтрация текстовых сообщений через `F.message.body.text`
- Индикатор действия `SenderAction.TYPING_ON`
- Запуск через `start_polling()`

**Аналог в Telegram:** `python-telegram-bot` EchoBot / `aiogram` echo_bot

---

### 02. Форматирование текста

**Файл:** [`02_formatting_bot.py`](02_formatting_bot.py)

Демонстрация всех видов форматирования: жирный, курсив, код, ссылки, упоминания. Поддержка HTML и Markdown.

**Что изучите:**
- `Bold`, `Italic`, `Underline`, `Strikethrough`, `Code`, `Heading`
- `Link` (гиперссылка) и `UserMention` (упоминание пользователя)
- Контейнер `Text` для комбинирования элементов
- Методы `.as_html()` и `.as_markdown()`
- Параметр `format=TextFormat.HTML`

**Команды бота:** `/html`, `/markdown`, `/mention`

**Аналог в Telegram:** `parse_mode=HTML` / aiogram formatting helpers

---

### 03. Inline-клавиатуры и callbacks

**Файл:** [`03_keyboard_bot.py`](03_keyboard_bot.py)

Полный пример работы с кнопками: создание клавиатуры, обработка нажатий, редактирование сообщения, навигация «Назад».

**Что изучите:**
- `InlineKeyboardBuilder` — построитель клавиатуры
- Типы кнопок: `CallbackButton`, `LinkButton`, `RequestContactButton`, `RequestGeoLocationButton`
- Обработка `MessageCallback`
- Обязательный `event.answer()` для подтверждения нажатия
- Редактирование сообщения с клавиатурой через `bot.edit_message()`
- Навигация «Назад» — возврат к предыдущему экрану

**Аналог в Telegram:** `InlineKeyboardMarkup` / `CallbackQueryHandler`

---

### 04. FSM — пошаговая форма регистрации

**Файл:** [`04_fsm_bot.py`](04_fsm_bot.py)

Бот собирает данные пользователя пошагово: имя → возраст → город → подтверждение. С валидацией ввода и возможностью отмены.

**Что изучите:**
- `StatesGroup` и `State` — определение состояний
- `BaseContext` — хранилище данных между шагами
- `context.set_state()` — переход между состояниями
- `context.update_data()` — сохранение данных
- `context.get_data()` — получение накопленных данных
- `context.clear()` — сброс (команда `/cancel`)
- Валидация: проверка что возраст — число от 1 до 120
- Inline-кнопки подтверждения в финальном шаге

**Аналог в Telegram:** `ConversationHandler` (PTB) / `StatesGroup` + `FSMContext` (aiogram)

---

### 05. Работа с медиа-файлами

**Файл:** [`05_media_bot.py`](05_media_bot.py)

Отправка изображений из файла и буфера, предварительная загрузка для рассылок, обработка входящих вложений, пересылка сообщений.

**Что изучите:**
- `InputMedia(path=...)` — отправка файла с диска
- `InputMediaBuffer(buffer=..., filename=...)` — отправка из памяти
- `bot.upload_media()` — предварительная загрузка (токен для повторного использования)
- Обработка входящих вложений: определение типа (image, video, audio, file)
- `event.message.forward(chat_id=...)` — пересылка сообщения
- `SenderAction.SENDING_PHOTO` / `SENDING_VIDEO` / `SENDING_FILE`

**Аналог в Telegram:** `send_photo`, `send_document`, `send_audio`, `forward_message`

---

### 06. Администрирование чата

**Файл:** [`06_admin_bot.py`](06_admin_bot.py)

Команды управления сообщениями и участниками: закрепление, удаление, редактирование. Приветствие новых участников.

**Что изучите:**
- `bot.pin_message()` — закрепление сообщения
- `bot.delete_message()` — удаление сообщения
- `bot.edit_message()` — редактирование текста и вложений
- `bot.get_chat_by_id()` — информация о чате
- `bot.get_members_chat()` — список участников
- Обработка событий `user_added` и `user_removed`
- Обработка `chat_title_changed`

**Команды бота:** `/pin`, `/delete`, `/edit`, `/info`, `/members`

**Аналог в Telegram:** `pin_chat_message`, `delete_message`, `edit_message_text`

---

### 07. Модульная архитектура с роутерами

**Файл:** [`07_router_bot.py`](07_router_bot.py)

Структурирование бота через роутеры: разделение обработчиков по модулям, фильтры и middleware на уровне роутера.

**Что изучите:**
- `Router(router_id=...)` — создание роутера
- `dp.include_routers()` — подключение роутеров к диспетчеру
- `BaseFilter` — кастомный фильтр (только для группового чата)
- Middleware на уровне роутера (логирование действий администратора)
- Изоляция обработчиков между роутерами
- Паттерн: general / admin / feature роутеры

**Аналог в Telegram:** aiogram `Router` / `include_router()`

---

### 08. Middleware паттерны

**Файл:** [`08_middleware_bot.py`](08_middleware_bot.py)

Четыре типа middleware: логирование, rate limiting, авторизация, обработка ошибок.

**Что изучите:**
- `BaseMiddleware` — базовый класс middleware
- `LoggingMiddleware` — логирование всех событий
- `ThrottleMiddleware` — ограничение частоты (1 сообщение/сек на пользователя)
- `AuthMiddleware` — whitelist разрешённых пользователей
- `ErrorHandlingMiddleware` — перехват ошибок без падения бота
- `dp.outer_middleware()` vs `dp.middleware()` — порядок в цепочке
- Передача данных через `data` dict в хендлер

**Аналог в Telegram:** aiogram `BaseMiddleware`

---

### 09. Webhook с FastAPI

**Файл:** [`09_webhook_bot.py`](09_webhook_bot.py)

Продакшн-интеграция через FastAPI: webhook-эндпоинт, подписка, secret, кастомные маршруты.

**Что изучите:**
- `FastAPIMaxWebhook` — интеграция с FastAPI
- `webhook.lifespan` — инициализация при старте сервера
- `bot.subscribe_webhook(url=..., secret=...)` — подписка на обновления
- Проверка `secret` через заголовок `X-Max-Bot-Api-Secret`
- Кастомные маршруты (`/healthz`, `/bot-info`) рядом с webhook
- Конфигурация через переменные окружения
- Запуск через `uvicorn`

**Требует:** `pip install maxapi[fastapi]`

**Аналог в Telegram:** `set_webhook` / aiogram webhook handler

---

### 10. Типизированные callback payloads — каталог товаров

**Файл:** [`10_callback_payload_bot.py`](10_callback_payload_bot.py)

Сложная навигация с типизированными payloads: каталог категорий → товары → детали → покупка → назад.

**Что изучите:**
- `CallbackPayload` с `prefix` — типизированный payload
- `.pack()` — сериализация payload в строку для кнопки
- `.filter()` — фильтр для хендлера по типу payload
- Получение типизированного объекта `payload: MyPayload` в хендлере
- Навигация «Назад» с сохранением контекста (category_id)
- Fallback-хендлер для неизвестных callback

**Аналог в Telegram:** aiogram `CallbackData` с `prefix`

---

## Структура примера

Каждый файл следует единой структуре:

```python
"""
Описание бота и что он демонстрирует.

Аналог Telegram: ...

Запуск:
    MAX_BOT_TOKEN=your_token python XX_example.py
"""

# Импорты
from maxapi import Bot, Dispatcher

# Инициализация
bot = Bot()      # Токен из MAX_BOT_TOKEN
dp = Dispatcher()

# Обработчики
@dp.message_created(...)
async def handler(event):
    ...

# Запуск
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
```

## Частые вопросы

**Бот не запускается — `InvalidToken` / `MAX_BOT_TOKEN не может быть None`**
Токен не найден в переменных окружения. Убедитесь что выполнили `export MAX_BOT_TOKEN="ваш_токен"` в текущей сессии терминала, или используйте `.env` файл с `load_dotenv()` (см. [Подготовка окружения](#3-настройка-токена)).

**Бот не отвечает в групповом чате**
Дайте боту права администратора в настройках чата.

**Чем `event.message.answer()` отличается от `bot.send_message()`?**
`answer()` — это удобная обёртка, которая автоматически подставляет `chat_id` и `user_id` из входящего сообщения. `bot.send_message()` требует указать их явно. Используйте `answer()` для ответов и `bot.send_message()` для отправки в произвольный чат.

**Что такое `BotStarted`? В Telegram такого нет.**
В MAX есть кнопка «Начать» в диалоге с ботом. Когда пользователь нажимает её, приходит событие `BotStarted`. Это аналог `/start`, но без текстового сообщения. Рекомендуется обрабатывать оба: `@dp.bot_started()` и `@dp.message_created(CommandStart())`.

**Как включить debug-логирование?**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```
Логгеры библиотеки: `bot`, `dispatcher`, `connection`.

**Как перейти с polling на webhook?**
Смотрите пример [`09_webhook_bot.py`](09_webhook_bot.py). Не забудьте удалить подписки polling через `await bot.delete_webhook()` если они были.

**Как хранить состояние между перезагрузками?**
Используйте `RedisContext` вместо `MemoryContext`:
```python
import redis.asyncio as redis
dp = Dispatcher(
    storage=RedisContext,
    redis_client=redis.from_url("redis://localhost"),
)
```
Подробнее в [документации](https://love-apples.github.io/maxapi/context/context/).

**Можно ли запустить бота на сервере?**
Да. Для polling — запустите скрипт через `systemd`, `supervisor` или `docker`. Для webhook — разверните за nginx/caddy и используйте пример [`09_webhook_bot.py`](09_webhook_bot.py).

## Миграция с Telegram (aiogram)

Если вы переходите с aiogram — вот ключевые отличия:

| Концепция | aiogram | maxapi |
|-----------|---------|--------|
| Хендлер получает | `message: Message` | `event: MessageCreated` (обёртка с `event.message`) |
| Текст сообщения | `message.text` | `event.message.body.text` |
| Callback data | `callback.data` | `event.callback.payload` |
| Ответ на callback | `callback.answer()` | `event.answer()` |
| Кнопка «Начать» | Нет (только `/start`) | `BotStarted` — отдельное событие |
| Регистрация хендлера | `@dp.message(CommandStart())` | `@dp.message_created(CommandStart())` |
| Polling | `dp.start_polling()` | `dp.start_polling(bot)` — бот передаётся явно |
| FSM контекст | `state: FSMContext` | `context: BaseContext` |
| Callback data класс | `CallbackData(prefix="...")` | `CallbackPayload(prefix="...")` |
| Фильтр текста | `F.text` | `F.message.body.text` |
| Отправка файла | `FSInputFile("path")` | `InputMedia(path="path")` |
