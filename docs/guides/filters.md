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
@dp.message_created(F.message.body.attachments)
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

## ContactFilter (сообщения с контактом)

Фильтр срабатывает на `MessageCreated` и `MessageEdited`, если в сообщении есть
вложение типа `contact`. При совпадении возвращает `dict` с ключом `contact`,
который будет прокинут в хэндлер как аргумент.

```python
from maxapi.filters.contact import ContactFilter
from maxapi.types.attachments.contact import Contact


@dp.message_created(ContactFilter())
async def on_contact(event, contact: Contact):
    # contact.payload.vcf_info — исходная VCF строка (не изменяется)
    # contact.payload.vcf — высокоуровневый доступ к распарсенному vCard
    full_name = contact.payload.vcf.full_name
    phone = contact.payload.vcf.phone
    await event.message.answer(f"{full_name=}, {phone=}")
```

Если нужно разобрать VCF вручную, можно использовать `parse_vcf_info`:

```python
from maxapi.utils.vcf import parse_vcf_info

info = parse_vcf_info(contact.payload.vcf_info)
print(info.full_name, info.phones)
```

## ChannelPostFilter (посты из канала)

Фильтр срабатывает на `MessageCreated` и `MessageEdited`, если сообщение пришло
из **канала** (то есть `recipient.chat_type == ChatType.CHANNEL`).

```python
from maxapi.filters.channel_post import ChannelPostFilter
from maxapi.types import MessageCreated


@dp.message_created(ChannelPostFilter())
async def on_channel_post(event: MessageCreated):
    await event.message.answer("Пост из канала получен")
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
