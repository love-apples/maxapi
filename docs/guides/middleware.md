# Middleware

Middleware позволяет обрабатывать события до и после обработчиков.

## Создание middleware

```python
from maxapi.filters.middleware import BaseMiddleware
from typing import Any, Awaitable, Callable, Dict

class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event_object: Any,
        data: Dict[str, Any],
    ) -> Any:
        print(f"Обработка события: {event_object.update_type}")
        result = await handler(event_object, data)
        print(f"Обработка завершена")
        return result
```

## Глобальный middleware

```python
dp.middleware(LoggingMiddleware())
```

## Middleware в обработчике

```python
@dp.message_created(Command('start'), LoggingMiddleware())
async def start_handler(event: MessageCreated):
    await event.message.answer("Привет!")
```

## Middleware с данными

```python
class CustomDataMiddleware(BaseMiddleware):
    async def __call__(self, handler, event_object, data):
        data['custom_data'] = f'User ID: {event_object.from_user.user_id}'
        return await handler(event_object, data)

@dp.message_created(Command('data'), CustomDataMiddleware())
async def handler(event: MessageCreated, custom_data: str):
    await event.message.answer(custom_data)
```

## Примеры использования

- Логирование
- Авторизация
- Обработка ошибок
- Измерение времени выполнения
- Модификация данных
