# Примеры

Здесь собраны практические примеры использования MaxAPI для различных задач.

## Эхо-бот

Простейший пример бота, который повторяет все текстовые сообщения:

```python
import asyncio
import logging

from maxapi import Bot, Dispatcher, F
from maxapi.types import MessageCreated

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()


@dp.message_created(F.message.body.text)
async def echo(event: MessageCreated):
    await event.message.answer(f"Повторяю за вами: {event.message.body.text}")


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
```

## Обработка событий

Пример обработки различных событий, доступных в MaxAPI:

```python
import asyncio
import logging

from maxapi import Bot, Dispatcher
from maxapi.types import (
    BotStarted, 
    Command, 
    MessageCreated, 
    CallbackButton, 
    MessageCallback, 
    BotAdded, 
    ChatTitleChanged, 
    MessageEdited, 
    MessageRemoved, 
    UserAdded, 
    UserRemoved,
    BotStopped,
    DialogCleared,
    DialogMuted,
    DialogUnmuted,
    ChatButton,  # deprecated: 0.9.14
    MessageChatCreated  # deprecated: 0.9.14
)
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()


@dp.message_created(Command('start'))
async def hello(event: MessageCreated):
    builder = InlineKeyboardBuilder()

    builder.row(
        CallbackButton(
            text='Кнопка 1',
            payload='btn_1'
        ),
        CallbackButton(
            text='Кнопка 2',
            payload='btn_2',
        )
    )
    builder.add(
        ChatButton(  # deprecated: 0.9.14
            text='Создать чат',
            chat_title='Тест чат'
        )
    )

    await event.message.answer(
        text='Привет!', 
        attachments=[
            builder.as_markup(),
        ]
    )


@dp.bot_added()
async def bot_added(event: BotAdded):
    if not event.chat:
        logging.info('Не удалось получить chat, возможно отключен auto_requests!')
        return
    
    await bot.send_message(
        chat_id=event.chat_id,
        text=f'Привет чат {event.chat.title}!'
    )


@dp.message_removed()
async def message_removed(event: MessageRemoved):
    await bot.send_message(
        chat_id=event.chat_id,
        text='Я всё видел!'
    )


@dp.bot_started()
async def bot_started(event: BotStarted):
    await bot.send_message(
        chat_id=event.chat_id,
        text='Привет! Отправь мне /start'
    )


@dp.chat_title_changed()
async def chat_title_changed(event: ChatTitleChanged):
    await bot.send_message(
        chat_id=event.chat_id,
        text=f'Крутое новое название "{event.title}"!'
    )


@dp.message_callback()
async def message_callback(event: MessageCallback):
    await event.answer(
        new_text=f'Вы нажали на кнопку {event.callback.payload}!'
    )


@dp.message_edited()
async def message_edited(event: MessageEdited):
    await event.message.answer(
        text='Вы отредактировали сообщение!'
    )


@dp.user_removed()
async def user_removed(event: UserRemoved):
    if not event.from_user:
        return await bot.send_message(
            chat_id=event.chat_id,
            text=f'Неизвестный кикнул {event.user.first_name} 😢'
        )
        
    await bot.send_message(
        chat_id=event.chat_id,
        text=f'{event.from_user.first_name} кикнул {event.user.first_name} 😢'
    )


@dp.user_added()
async def user_added(event: UserAdded):
    if not event.chat:
        return await bot.send_message(
            chat_id=event.chat_id,
            text=f'Чат приветствует вас, {event.user.first_name}!'
        )
        
    await bot.send_message(
        chat_id=event.chat_id,
        text=f'Чат "{event.chat.title}" приветствует вас, {event.user.first_name}!'
    )


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
```

## MagicFilter

Использование MagicFilter для гибкой фильтрации сообщений:

```python
import asyncio
import logging

from maxapi import Bot, Dispatcher, F
from maxapi.types import MessageCreated

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()


@dp.message_created(F.message.body.text == 'привет')
async def on_hello(event: MessageCreated):
    await event.message.answer('Привет!')


@dp.message_created(F.message.body.text.lower().contains('помощь'))
async def on_help(event: MessageCreated):
    await event.message.answer('Чем могу помочь?')


@dp.message_created(F.message.body.text.regexp(r'^\d{4}$'))
async def on_code(event: MessageCreated):
    await event.message.answer('Принят 4-значный код')


@dp.message_created(F.message.body.attachments)
async def on_attachment(event: MessageCreated):
    await event.message.answer('Получено вложение')


@dp.message_created(F.message.body.text.len() > 20)
async def on_long_text(event: MessageCreated):
    await event.message.answer('Слишком длинное сообщение')


@dp.message_created(F.message.body.text.len() > 0)
async def on_non_empty(event: MessageCreated):
    await event.message.answer('Вы что-то написали.')


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
```

## Клавиатуры

Примеры работы с различными типами кнопок и клавиатур:

```python
import asyncio
import logging

from maxapi import Bot, Dispatcher
from maxapi.types import (
    ChatButton,  # deprecated: 0.9.14
    LinkButton, 
    CallbackButton, 
    RequestGeoLocationButton, 
    MessageButton, 
    ButtonsPayload,
    RequestContactButton, 
    OpenAppButton,
    MessageCreated, 
    MessageCallback, 
    MessageChatCreated, # deprecated: 0.9.14
    CommandStart, 
    Command
)
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()


@dp.message_created(CommandStart())
async def echo(event: MessageCreated):
    await event.message.answer(
        (
            'Привет! Мои команды:\n\n'
            
            '/builder - Клавиатура из InlineKeyboardBuilder\n'
            '/payload - Клавиатура из pydantic моделей\n'
        )
    )
    
    
@dp.message_created(Command('builder'))
async def builder(event: MessageCreated):
    builder = InlineKeyboardBuilder()
    
    builder.row(
        ChatButton(  # deprecated: 0.9.14
            text="Создать чат", 
            chat_title='Test', 
            chat_description='Test desc'
        ),
        LinkButton(
            text="Документация MAX", 
            url="https://dev.max.ru/docs"
        ),
    )
    
    builder.row(
        RequestGeoLocationButton(text="Геолокация"),
        MessageButton(text="Сообщение"),
    )
    
    builder.row(
        RequestContactButton(text="Контакт"),
        OpenAppButton(
            text="Приложение", 
            web_app=event.bot.me.username, 
            contact_id=event.bot.me.user_id
        ),
    )
    
    builder.row(
        CallbackButton(
            text='Callback',
            payload='test',
        )
    )
    
    await event.message.answer(
        text='Клавиатура из InlineKeyboardBuilder',
        attachments=[
            builder.as_markup()
        ])
    
    
@dp.message_created(Command('payload'))
async def payload(event: MessageCreated):
    buttons = [
        [
            ChatButton(  # deprecated: 0.9.14
                text="Создать чат", 
                chat_title='Test', 
                chat_description='Test desc'
            ),
            LinkButton(
                text="Документация MAX", 
                url="https://dev.max.ru/docs"
            ),
        ],
        [
            RequestGeoLocationButton(text="Геолокация"),
            MessageButton(text="Сообщение"),
        ],
        [
            RequestContactButton(text="Контакт"),
            OpenAppButton(
                text="Приложение", 
                web_app=event.bot.me.username, 
                contact_id=event.bot.me.user_id
            ),
        ],
        [
            CallbackButton(
                text='Callback',
                payload='test',
            )
        ]
    ]
    
    buttons_payload = ButtonsPayload(buttons=buttons).pack()
    
    await event.message.answer(
        text='Клавиатура из pydantic моделей',
        attachments=[
            buttons_payload
        ])
    
    
@dp.message_chat_created()  # deprecated: 0.9.14
async def message_chat_created(obj: MessageChatCreated):
    await obj.bot.send_message(
        chat_id=obj.chat.chat_id,
        text=f'Чат создан! Ссылка: {obj.chat.link}'
    )
    

@dp.message_callback()
async def message_callback(callback: MessageCallback):
    await callback.message.answer('Вы нажали на Callback!')


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
```

## Получение ID

Пример получения различных ID из событий:

```python
import asyncio
import logging

from maxapi import Bot, Dispatcher, F
from maxapi.enums.parse_mode import ParseMode
from maxapi.types import MessageCreated

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()


@dp.message_created(F.message.link.type == 'forward')
async def get_ids_from_forward(event: MessageCreated):
    text = (
        'Информация о пересланном сообщении:\n\n'
        
        f'Из чата: <b>{event.message.link.chat_id}</b>\n'
        f'От пользователя: <b>{event.message.link.sender.user_id}</b>'
    )
    await event.message.reply(text)
    

@dp.message_created()
async def get_ids(event: MessageCreated):
    text = (
        f'Ваш ID: <b>{event.from_user.user_id}</b>\n'
        f'ID этого чата: <b>{event.chat.chat_id}</b>'
    )
    await event.message.answer(text, parse_mode=ParseMode.HTML)


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
```

## Создание собственного фильтра

Пример создания кастомного фильтра на основе `BaseFilter`:

```python
import asyncio
import logging

from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated, CommandStart, UpdateUnion
from maxapi.filters import BaseFilter

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()


class FilterChat(BaseFilter):
    
    """
    Фильтр, который срабатывает только в чате с названием `Test`
    """
    
    async def __call__(self, event: UpdateUnion):
        
        if not event.chat:
            return False
        
        return event.chat == 'Test'


@dp.message_created(CommandStart(), FilterChat())
async def custom_data(event: MessageCreated):
    await event.message.answer('Привет!')


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
```

## Фильтр callback payload

Пример использования типизированных payload для callback-кнопок:

```python
import asyncio
import logging

from maxapi import Bot, Dispatcher, F
from maxapi.filters.callback_payload import CallbackPayload
from maxapi.filters.command import CommandStart
from maxapi.types import (
    CallbackButton,
    MessageCreated,
    MessageCallback,
)
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()


class MyPayload(CallbackPayload, prefix='mypayload'):
    foo: str
    action: str


class AnotherPayload(CallbackPayload, prefix='another'):
    bar: str
    value: int


@dp.message_created(CommandStart())
async def show_keyboard(event: MessageCreated):
    kb = InlineKeyboardBuilder()
    kb.row(
        CallbackButton( 
            text='Первая кнопка',
            payload=MyPayload(foo='123', action='edit').pack(), 
        ), 
        CallbackButton(
            text='Вторая кнопка',
            payload=AnotherPayload(bar='abc', value=42).pack(),
        ),
    )
    await event.message.answer('Нажми кнопку!', attachments=[kb.as_markup()])


@dp.message_callback(MyPayload.filter(F.foo == '123'))
async def on_first_callback(event: MessageCallback, payload: MyPayload):
    await event.answer(new_text=f'Первая кнопка: foo={payload.foo}, action={payload.action}')


@dp.message_callback(AnotherPayload.filter())
async def on_second_callback(event: MessageCallback, payload: AnotherPayload):
    await event.answer(new_text=f'Вторая кнопка: bar={payload.bar}, value={payload.value}')


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
```

## Middleware в обработчиках

Пример использования middleware на уровне обработчиков:

```python
import asyncio
import logging

from typing import Any, Awaitable, Callable, Dict

from maxapi import Bot, Dispatcher
from maxapi.filters.middleware import BaseMiddleware
from maxapi.types import MessageCreated, Command, UpdateUnion

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()


class CheckChatTitleMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event_object: UpdateUnion,
        data: Dict[str, Any],
    ) -> Any:
        
        if event_object.chat.title == 'MAXApi':
            return await handler(event_object, data)


class CustomDataMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event_object: UpdateUnion,
        data: Dict[str, Any],
    ) -> Any:
        
        data['custom_data'] = f'Это ID того кто вызвал команду: {event_object.from_user.user_id}'
        
        await handler(event_object, data)


@dp.message_created(Command('start'), CheckChatTitleMiddleware())
async def start(event: MessageCreated):
    await event.message.answer('Это сообщение было отправлено, так как ваш чат называется "MAXApi"!')

    
@dp.message_created(Command('custom_data'), CustomDataMiddleware())
async def custom_data(event: MessageCreated, custom_data: str):
    await event.message.answer(custom_data)
    
    
@dp.message_created(Command('many_middlewares'), CheckChatTitleMiddleware(), CustomDataMiddleware())
async def many_middlewares(event: MessageCreated, custom_data: str):
    await event.message.answer('Это сообщение было отправлено, так как ваш чат называется "MAXApi"!')
    await event.message.answer(custom_data)
    

async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
```

## Middleware в роутерах

Пример использования middleware на уровне роутера:

```python
import asyncio
import logging

from typing import Any, Awaitable, Callable, Dict

from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated, Command, UpdateUnion
from maxapi.filters.middleware import BaseMiddleware

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()


class CustomDataForRouterMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event_object: UpdateUnion,
        data: Dict[str, Any],
    ) -> Any:
        
        data['custom_data'] = f'Это ID того кто вызвал команду: {event_object.from_user.user_id}'
        result = await handler(event_object, data)
        return result
    

@dp.message_created(Command('custom_data'))
async def custom_data(event: MessageCreated, custom_data: str):
    await event.message.answer(custom_data)
    
    
async def main():
    dp.middleware(CustomDataForRouterMiddleware())
    
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
```

## Роутеры, InputMedia и контекст

Пример использования роутеров, InputMedia и работы с контекстом и состояниями:

```python
import asyncio
import logging

from maxapi import Bot, Dispatcher, F
from maxapi.context import MemoryContext, State, StatesGroup
from maxapi.types import BotStarted, Command, MessageCreated, CallbackButton, MessageCallback, BotCommand
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from router import router

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()

dp.include_routers(router)


start_text = '''Пример чат-бота для MAX 💙

Мои команды:

/clear очищает ваш контекст
/state или /context показывают ваше контекстное состояние
/data показывает вашу контекстную память
'''


class Form(StatesGroup):
    name = State()
    age = State()


@dp.on_started()
async def _():
    logging.info('Бот стартовал!')


@dp.bot_started()
async def bot_started(event: BotStarted):
    await event.bot.send_message(
        chat_id=event.chat_id,
        text='Привет! Отправь мне /start'
    )


@dp.message_created(Command('clear'))
async def hello(event: MessageCreated, context: MemoryContext):
    await context.clear()
    await event.message.answer(f"Ваш контекст был очищен!")


@dp.message_created(Command('data'))
async def hello(event: MessageCreated, context: MemoryContext):
    data = await context.get_data()
    await event.message.answer(f"Ваша контекстная память: {str(data)}")


@dp.message_created(Command('context'))
@dp.message_created(Command('state'))
async def hello(event: MessageCreated, context: MemoryContext):
    data = await context.get_state()
    await event.message.answer(f"Ваше контекстное состояние: {str(data)}")


@dp.message_created(Command('start'))
async def hello(event: MessageCreated):
    builder = InlineKeyboardBuilder()

    builder.row(
        CallbackButton(
            text='Ввести свое имя',
            payload='btn_1'
        ),
        CallbackButton(
            text='Ввести свой возраст',
            payload='btn_2'
        )
    )
    builder.row(
        CallbackButton(
            text='Не хочу',
            payload='btn_3'
        )
    )

    await event.message.answer(
        text=start_text, 
        attachments=[
            builder.as_markup(),
        ]
    )
    

@dp.message_callback(F.callback.payload == 'btn_1')
async def hello(event: MessageCallback, context: MemoryContext):
    await context.set_state(Form.name)
    await event.message.delete()
    await event.message.answer(f'Отправьте свое имя:')


@dp.message_callback(F.callback.payload == 'btn_2')
async def hello(event: MessageCallback, context: MemoryContext):
    await context.set_state(Form.age)
    await event.message.delete()
    await event.message.answer(f'Отправьте ваш возраст:')


@dp.message_callback(F.callback.payload == 'btn_3')
async def hello(event: MessageCallback, context: MemoryContext):
    await event.message.delete()
    await event.message.answer(f'Ну ладно 🥲')


@dp.message_created(F.message.body.text, Form.name)
async def hello(event: MessageCreated, context: MemoryContext):
    await context.update_data(name=event.message.body.text)

    data = await context.get_data()

    await event.message.answer(f"Приятно познакомиться, {data['name'].title()}!")
    

@dp.message_created(F.message.body.text, Form.age)
async def hello(event: MessageCreated, context: MemoryContext):
    await context.update_data(age=event.message.body.text)

    await event.message.answer(f"Ого! А мне всего пару недель 😁")


async def main():
    await bot.set_my_commands(
        BotCommand(
            name='/start',
            description='Перезапустить бота'
        ),
        BotCommand(
            name='/clear',
            description='Очищает ваш контекст'
        ),
        BotCommand(
            name='/state',
            description='Показывают ваше контекстное состояние'
        ),
        BotCommand(
            name='/data',
            description='Показывает вашу контекстную память'
        ),
        BotCommand(
            name='/context',
            description='Показывают ваше контекстное состояние'
        )
    )
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
```

И соответствующий роутер (`router.py`):

```python
from maxapi import F, Router
from maxapi.types import Command, MessageCreated
from maxapi.types import InputMedia

router = Router()
file = __file__.split('\\')[-1]


@router.message_created(Command('router'))
async def hello(obj: MessageCreated):
    await obj.message.answer(f"Пишу тебе из роута {file}")
    

# новая команда для примера, /media, 
# пример использования: /media image.png (медиафайл берется указанному пути)
@router.message_created(Command('media'))
async def hello(event: MessageCreated):
    await event.message.answer(
        attachments=[
            InputMedia(
                path=event.message.body.text.replace('/media ', '')
            )
        ]
    )
```

## Webhook

### Высокоуровневый подход

Простой способ работы с webhook через встроенный метод:

```python
import asyncio
import logging

from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()


@dp.message_created()
async def handle_message(event: MessageCreated):
    await event.message.answer('Бот работает через вебхук!')


async def main():
    await dp.handle_webhook(
        bot=bot, 
        host='localhost',
        port=8080,
        log_level='critical'
    )


if __name__ == '__main__':
    asyncio.run(main())
```

### Низкоуровневый подход

Более гибкий способ с использованием FastAPI:

```python
import asyncio
import logging

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
except ImportError:
    raise ImportError(
        '\n\t Не установлен fastapi!'
        '\n\t Выполните команду для установки fastapi: '
        '\n\t pip install fastapi>=0.68.0'
        '\n\t Или сразу все зависимости для работы вебхука:'
        '\n\t pip install maxapi[webhook]'
    )

from maxapi import Bot, Dispatcher
from maxapi.methods.types.getted_updates import process_update_webhook
from maxapi.types import MessageCreated

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()

 
@dp.message_created()
async def handle_message(event: MessageCreated):
    await event.message.answer('Бот работает через вебхук!')

# Регистрация обработчика для вебхука
@dp.webhook_post('/')
async def _(request: Request):
    
    # Сериализация полученного запроса
    event_json = await request.json()
    
    # Десериализация полученного запроса в pydantic
    event_object = await process_update_webhook(
        event_json=event_json,
        bot=bot
    )
    
    # ...свой код
    print(f'Информация из вебхука: {event_json}')
    # ...свой код

    # Окончательная обработка запроса
    await dp.handle(event_object)
    
    # Ответ вебхука
    return JSONResponse(content={'ok': True}, status_code=200)


async def main():
    # Запуск сервера
    await dp.init_serve(bot, log_level='critical')


if __name__ == '__main__':
    asyncio.run(main())
```

## Настройка прокси

### Подключение через прокси

Для использования прокси-сервера передайте параметр `proxy` в `DefaultConnectionProperties`:

```python
import asyncio
from maxapi import Bot, Dispatcher
from maxapi.client import DefaultConnectionProperties
from maxapi.types import MessageCreated, Command

# URL прокси в формате: http://login:password@ip:port
proxy_url = "http://login:password@ip:port"

# Создание настроек соединения с прокси
connection_props = DefaultConnectionProperties(proxy=proxy_url)

# Инициализация бота с настройками соединения
bot = Bot(default_connection=connection_props)
dp = Dispatcher()

@dp.message_created(Command('start'))
async def start_handler(event: MessageCreated):
    await event.message.answer("Привет!")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
```

### Использование прокси из переменных окружения

Для использования прокси из переменных окружения используйте параметр `trust_env=True`:

```python
import asyncio
from maxapi import Bot, Dispatcher
from maxapi.client import DefaultConnectionProperties
from maxapi.types import MessageCreated, Command

bot = Bot(
    "YOUR-TOKEN",
    default_connection=DefaultConnectionProperties(trust_env=True),
)
dp = Dispatcher()

@dp.message_created(Command('start'))
async def start_handler(event: MessageCreated):
    await event.message.answer("Привет!")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
```

#### Что такое `trust_env`?

Параметр `trust_env=True` в aiohttp позволяет автоматически читать настройки прокси из переменных окружения системы. Когда этот параметр включен, aiohttp будет искать следующие переменные окружения:

- **`HTTP_PROXY`** — прокси для HTTP-запросов (например, `http://proxy.example.com:8080`)
- **`HTTPS_PROXY`** — прокси для HTTPS-запросов (например, `https://proxy.example.com:8080`)
- **`NO_PROXY`** — список доменов, для которых прокси не используется (например, `localhost,127.0.0.1,*.local`)

**Важно**: Если переменные окружения не установлены, `trust_env=True` не вызовет ошибку — просто прокси использоваться не будет.
