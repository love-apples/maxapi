# Обработчики событий

## Синтаксис

```python
@dp.<тип_события>(<фильтры>, <middleware>, ...)
async def handler(event: <тип_события>, context: MemoryContext, ...):
    ...
```

## Примеры

### Обработка команды

```python
from maxapi.types import MessageCreated, Command

@dp.message_created(Command('start'))
async def start_handler(event: MessageCreated):
    await event.message.answer("Привет!")
```

### Обработка с фильтром

```python
from maxapi import F

@dp.message_created(F.message.body.text)
async def text_handler(event: MessageCreated):
    await event.message.answer(f"Вы написали: {event.message.body.text}")
```

### Обработка без фильтра

```python
@dp.message_created()
async def any_message(event: MessageCreated):
    await event.message.answer("Получено сообщение")
```

### Комбинация фильтров и состояний

```python
from maxapi.context import State, StatesGroup

class Form(StatesGroup):
    name = State()

@dp.message_created(F.message.body.text, Form.name)
async def name_handler(event: MessageCreated, context: MemoryContext):
    await context.update_data(name=event.message.body.text)
    await event.message.answer(f"Привет, {event.message.body.text}!")
```

### Обработка с контекстом

```python
@dp.message_created(Command('data'))
async def data_handler(event: MessageCreated, context: MemoryContext):
    data = await context.get_data()
    await event.message.answer(f"Данные: {data}")
```

## Доступные события

### События сообщений

- `message_created` — создание нового сообщения
- `message_edited` — редактирование сообщения
- `message_removed` — удаление сообщения
- `message_callback` — нажатие на callback-кнопку
- `message_chat_created` — создание чата через сообщение

### События бота

- `bot_added` — бот добавлен в чат
- `bot_removed` — бот удален из чата
- `bot_started` — пользователь нажал кнопку "Начать" с ботом
- `bot_stopped` — бот остановлен

### События пользователей

- `user_added` — пользователь добавлен в чат
- `user_removed` — пользователь удален из чата

### События чата

- `chat_title_changed` — изменено название чата

### События диалога

- `dialog_cleared` — диалог очищен
- `dialog_muted` — диалог заглушен (уведомления отключены)
- `dialog_unmuted` — диалог разглушен (уведомления включены)
- `dialog_removed` — диалог удален

### Служебные события

- `on_started` — событие при старте диспетчера (после инициализации)

Подробнее о типах событий см. [Updates](../types/updates/index.md)
