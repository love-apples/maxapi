# Контекст и состояния

## MemoryContext

Встроенная система состояний для диалогов. Контекст автоматически передается в обработчики:

```python
from maxapi.context import MemoryContext, StatesGroup, State
from maxapi.types import MessageCreated, Command

class Form(StatesGroup):
    name = State()
    age = State()

@dp.message_created(Command('start'))
async def start_handler(event: MessageCreated, context: MemoryContext):
    await context.set_state(Form.name)
    await event.message.answer("Как вас зовут?")

@dp.message_created(Form.name)
async def name_handler(event: MessageCreated, context: MemoryContext):
    await context.update_data(name=event.message.body.text)
    await context.set_state(Form.age)
    await event.message.answer("Сколько вам лет?")

@dp.message_created(Form.age)
async def age_handler(event: MessageCreated, context: MemoryContext):
    data = await context.get_data()
    await event.message.answer(
        f"Приятно познакомиться, {data['name']}! "
        f"Вам {event.message.body.text} лет."
    )
    await context.set_state(None)  # Сброс состояния
```

## Методы MemoryContext

- `set_state(state)` — установить состояние (State или None для сброса)
- `get_state()` — получить текущее состояние
- `get_data()` — получить все данные контекста
- `update_data(**kwargs)` — обновить данные
- `set_data(data)` — полностью заменить данные
- `clear()` — очистить контекст и сбросить состояние

## StatesGroup

Группа состояний для FSM:

```python
class Form(StatesGroup):
    name = State()  # Автоматически получит имя 'Form:name'
    age = State()   # Автоматически получит имя 'Form:age'
```

## Фильтрация по состояниям

Вы можете ограничивать выполнение хендлеров определенными состояниями:

```python
# Только в состоянии Form.name
@dp.message_created(Form.name)
async def name_handler(event: MessageCreated, context: MemoryContext):
    ...

# Только когда НЕТ активного состояния
@dp.message_created(None)
async def no_state_handler(event: MessageCreated):
    ...

# В любом из перечисленных состояний
@dp.message_created(Form.name, Form.age)
async def multi_state_handler(event: MessageCreated):
    ...
```

## Хранение в Redis

Для сохранения состояний и данных между перезапусками бота можно использовать Redis.

### Установка зависимостей

```bash
pip install redis
```

### Пример использования

```python
import redis.asyncio as redis
from maxapi import Dispatcher
from maxapi.context import RedisContext

# Инициализация клиента Redis
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Передача RedisContext в Диспетчер
dp = Dispatcher(
    storage=RedisContext,
    redis_client=redis_client,
    key_prefix="my_bot"
)
```

`RedisContext` автоматически сериализует данные в JSON и поддерживает атомарные обновления через Lua-скрипты.

### Маркер обновлений (`get_updates`)

В MAX API у `get_updates` есть **маркер обновлений** — это внутренняя “позиция” в ленте событий (по сути, пагинация). Если запускать бота **без маркера**, API может начать отдавать **старые обновления** (с “начального” маркера), и бот будет повторно обрабатывать прошлые события.

Решение простое: **сохраняйте маркер** и **передавайте его в бота при старте**.

Ниже пример хранения маркера в Redis (асинхронный клиент), ровно как ключ `bot:marker`:

```python
import redis.asyncio as redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)


async def load_marker() -> str | None:
    return await r.get("bot:marker")


async def save_marker(marker: str) -> None:
    await r.set("bot:marker", marker)
```

Пример простого **глобального middleware**, который сохраняет текущий маркер в Redis после обработки события:

```python
from maxapi.filters.middleware import BaseMiddleware
from maxapi.types import UpdateUnion
from typing import Any, Awaitable, Callable


class SaveMarkerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[UpdateUnion, dict[str, Any]], Awaitable[Any]],
        event_object: UpdateUnion,
        data: dict[str, Any],
    ) -> Any:
        result = await handler(event_object, data)

        marker: int | None = event_object.bot.marker_updates
        if marker is not None:
            await save_marker(str(marker))

        return result
```

Использование (при старте загрузили маркер, установили через `set_marker_updates`, подключили middleware):

- при запуске загрузить маркер и установить через `bot.set_marker_updates(...)`, например в `async main()`:

```python
import asyncio
from maxapi import Bot, Dispatcher

bot = Bot()
dp = Dispatcher()
dp.register_outer_middleware(SaveMarkerMiddleware())

async def main() -> None:
    marker = await load_marker()  # str | None

    if marker is not None:
        bot.set_marker_updates(int(marker))

    await dp.start_polling(bot)


asyncio.run(main())
```

- во время работы middleware будет обновлять сохранённый маркер на основании `event_object.bot.marker_updates`.
