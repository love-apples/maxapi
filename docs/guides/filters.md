# Фильтры

Фильтры определяют, когда должен сработать обработчик. Можно использовать несколько фильтров одновременно.

## MagicFilter (F)

Гибкая система фильтрации через объект `F`:

```python
from maxapi import F

# Только текстовые сообщения
@dp.message_created(F.message.body.text)
async def text_handler(event: MessageCreated):
    ...

# Сообщения с вложениями
@dp.message_created(F.message.attachments)
async def attachment_handler(event: MessageCreated):
    ...

# Комбинация условий
from maxapi.enums.chat_type import ChatType

@dp.message_created(F.message.body.text & F.message.chat.type == ChatType.PRIVATE)
async def private_text_handler(event: MessageCreated):
    ...
```

## Command фильтр

```python
from maxapi.types import Command

# Одна команда
@dp.message_created(Command('start'))
async def start_handler(event: MessageCreated):
    ...

# Несколько команд
@dp.message_created(Command(['start', 'help', 'info']))
async def commands_handler(event: MessageCreated):
    ...
```

## Callback Payload фильтр

```python
from maxapi.filters.callback_payload import CallbackPayload

# Простой payload (строка)
@dp.message_callback(F.callback.payload == 'button_click')
async def callback_handler(event: MessageCallback):
    ...

# Структурированный payload (класс)
class MyPayload(CallbackPayload, prefix='mypayload'):
    action: str
    value: int

# Без дополнительных условий
@dp.message_callback(MyPayload.filter())
async def callback_handler(event: MessageCallback, payload: MyPayload):
    await event.answer(f"Action: {payload.action}, Value: {payload.value}")

# С дополнительным фильтром
@dp.message_callback(MyPayload.filter(F.action == 'edit'))
async def callback_handler(event: MessageCallback, payload: MyPayload):
    await event.answer(f"Edit action: {payload.value}")
```

## Комбинация фильтров

```python
# И (AND)
F.message.body.text & F.message.chat.type == ChatType.PRIVATE

# Или (OR)
F.message.body.text | F.message.attachments

# Отрицание (NOT)
~F.message.body.text

# Несколько фильтров в декораторе
@dp.message_created(F.message.body.text, Command('start'), Form.name)
async def handler(event: MessageCreated):
    ...
```

## Базовые фильтры (BaseFilter)

Можно создать собственный фильтр, наследуясь от `BaseFilter`:

```python
from maxapi.filters.filter import BaseFilter

class MyFilter(BaseFilter):
    async def __call__(self, event):
        # Возвращает True/False или dict с данными
        return True
```
