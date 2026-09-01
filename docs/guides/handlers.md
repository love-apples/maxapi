# Обработчики событий

## Синтаксис

### Регистрация через декоратор

```python
@dp.<тип_события>(<фильтры>, <middleware>, ...)
async def handler(event: <тип_события>, context: MemoryContext, ...):
    ...
```

### Регистрация через функцию

Вы также можете регистрировать хендлеры без использования декораторов:

```python
async def my_handler(event: MessageCreated):
    await event.message.answer("Привет!")

dp.message_created.register(my_handler, <фильтры>)
```

## Примеры

### Обработка команды

```python
from maxapi.types import MessageCreated, Command


@dp.message_created(Command("start"))
async def start_handler(event: MessageCreated):
    await event.message.answer("Привет!")
```

### Обработка без состояния (None)

Если вы хотите, чтобы хендлер срабатывал только тогда, когда у пользователя нет активного состояния в FSM, используйте `None`:

```python
@dp.message_created(None, Command("help"))
async def help_no_state(event: MessageCreated):
    await event.message.answer(
        "Вы запросили помощь вне контекста заполнения формы."
    )
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
@dp.message_created(Command("data"))
async def data_handler(event: MessageCreated, context: MemoryContext):
    data = await context.get_data()
    await event.message.answer(f"Данные: {data}")
```

### Отправка медиа по токену

Если у вас уже есть токен загруженного файла (например, вы получили его после загрузки медиа на сервер или из другого сообщения), вы можете отправить его, используя `AttachmentUpload`:

```python
from maxapi.types.attachments.upload import AttachmentUpload, AttachmentPayload
from maxapi.enums.upload_type import UploadType


@dp.message_created(Command("send_photo"))
async def send_photo_by_token(event: MessageCreated):
    # Создаем вложение, используя существующий токен
    attachment = AttachmentUpload(
        type=UploadType.IMAGE,
        payload=AttachmentPayload(token="ВАШ_ТОКЕН_ЗДЕСЬ"),
    )

    await event.message.answer(
        text="Вот ваше фото по токену",
        attachments=[attachment],
    )
```

## Доступные события

### События сообщений

- `message_created` — создание нового сообщения
- `message_edited` — редактирование сообщения
- `message_removed` — удаление сообщения
- `message_callback` — нажатие на callback-кнопку
- `message_chat_created` — создание чата через сообщение (устарело)

### События бота {#bot-events}

- `bot_added` — бот добавлен в чат
- `bot_removed` — бот удален из чата
- `bot_started` — пользователь нажал кнопку "Начать" с ботом
- `bot_stopped` — бот остановлен

!!! info "Как вести список чатов бота"
    Метод [`get_chats`](../methods/get_chats.md) устарел, а готового
    списка чатов API не отдаёт. Накапливайте `chat_id` сами: сохраняйте
    при `bot_added` и `bot_started`, удаляйте при `bot_removed` (для
    диалогов — при `bot_stopped`). Эти события приходят и через Long
    Polling, и через
    [`subscribe_webhook`](../methods/subscribe_webhook.md) — менять
    транспорт ради них не нужно.

    Храните список в постоянном хранилище (БД, Redis, файл): после
    перезапуска бота восстановить его через `GET /chats` уже нельзя, а
    старые чаты новых событий не пришлют. `set` в примере ниже — только
    для иллюстрации.

    ```python
    from maxapi.types import BotAdded, BotRemoved, BotStarted, BotStopped

    known_chats: set[int] = set()  # в проде — постоянное хранилище


    @dp.bot_added()
    async def on_bot_added(event: BotAdded):
        known_chats.add(event.chat_id)


    @dp.bot_started()
    async def on_bot_started(event: BotStarted):
        known_chats.add(event.chat_id)


    @dp.bot_removed()
    async def on_bot_removed(event: BotRemoved):
        known_chats.discard(event.chat_id)


    @dp.bot_stopped()
    async def on_bot_stopped(event: BotStopped):
        known_chats.discard(event.chat_id)
    ```

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
