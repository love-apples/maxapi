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
