# Роутеры

Роутеры позволяют модульно организовать обработчики. `Router` наследуется от `Dispatcher`.

## Создание роутера

```python
from maxapi import Router
from maxapi.types import MessageCreated, Command

router = Router(router_id="my_router")


@router.message_created(Command("help"))
async def help_handler(event: MessageCreated):
    await event.message.answer("Помощь")
```

## Подключение роутера

```python
from maxapi import Dispatcher

dp = Dispatcher()
dp.include_routers(router)  # Множественное число, можно несколько
```

## Фильтры для роутера

```python
from maxapi import F
from maxapi.enums.chat_type import ChatType
from maxapi.types import Command

router = Router()
router.filter(Command("help"))  # Базовый фильтр (BaseFilter)
router.filter(F.chat.type == ChatType.DIALOG)  # Личный диалог (MagicFilter)
```

## Middleware для роутера

```python
from maxapi.filters.middleware import BaseMiddleware


class RouterMiddleware(BaseMiddleware):
    async def __call__(self, handler, event_object, data):
        # Логика только для этого роутера
        return await handler(event_object, data)


router.register_outer_middleware(RouterMiddleware())
```
