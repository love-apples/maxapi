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

## Outer и inner: когда что вызывается

У `Dispatcher` (и `Router`) есть две явные категории middleware:

- **`register_outer_middleware(mw)`** — вызывается до проверки фильтров
  и state конкретного handler. Срабатывает на **каждое** подходящее
  событие, даже если handler в итоге будет пропущен. Подходит для
  логирования, трейсинга, request-id и т.п.
- **`register_inner_middleware(mw)`** — вызывается **только** когда
  конкретный handler прошёл все свои фильтры/state и будет реально
  исполнен. Подходит для транзакций БД, метрик времени handler,
  захвата распределённых блокировок и т.п.

```python
dp.register_outer_middleware(LoggingMiddleware())        # каждый update
dp.register_inner_middleware(DbTransactionMiddleware())  # только под handler
```

То же доступно на `Router`:

```python
router.register_outer_middleware(AuditMiddleware())
router.register_inner_middleware(LockMiddleware())
```

!!! warning "Deprecated"
    Безымянные `dp.middleware(mw)` / `router.middleware(mw)` и
    `dp.outer_middleware(mw)` / `router.outer_middleware(mw)`
    помечены как deprecated и выводят `DeprecationWarning`.
    Используйте явные `register_outer_middleware()` /
    `register_inner_middleware()`.

## Развёрнутый пример: admin-роутер с broadcast

Рассмотрим реальный сценарий: у бота есть два роутера — `admin_router`
для команды `/broadcast` и `fallback_router` для всех остальных
сообщений. Нам нужно:

- фиксировать **любую** попытку войти в admin-flow — в том числе
  неудачную (не-админ написал `/broadcast`);
- захватывать дорогой distributed lock **только** когда broadcast
  реально стартует.

```python
from maxapi import Bot, Dispatcher, Router
from maxapi.filters.command import Command
from maxapi.filters.filter import BaseFilter
from maxapi.filters.middleware import BaseMiddleware
from maxapi.types.updates.message_created import MessageCreated


# ── Фильтры ──────────────────────────────────────────────────────────────────

class IsAdmin(BaseFilter):
    """Пропускает только пользователей из списка администраторов."""

    ADMIN_IDS = {111222333}

    async def __call__(self, event: MessageCreated) -> bool:
        return event.message.sender.user_id in self.ADMIN_IDS


# ── Middleware ────────────────────────────────────────────────────────────────

class RequestIdMiddleware(BaseMiddleware):
    """Outer-global: проставляет уникальный request-id на каждое событие."""

    async def __call__(self, handler, event, data):
        import uuid
        data["request_id"] = str(uuid.uuid4())
        return await handler(event, data)


class DbTransactionMiddleware(BaseMiddleware):
    """Inner-global: открывает транзакцию БД только под реальный handler."""

    async def __call__(self, handler, event, data):
        # async with db.transaction():  ← здесь была бы настоящая транзакция
        print("→ транзакция открыта")
        result = await handler(event, data)
        print("← транзакция закрыта")
        return result


class AdminAccessLogMiddleware(BaseMiddleware):
    """Outer-router: фиксирует ЛЮБУЮ попытку войти в admin-flow.

    Регистрируется как outer, чтобы срабатывать даже тогда, когда
    IsAdmin отклонит запрос. Именно так — security-аудит не пропустит
    перебор команд от не-администраторов.
    """

    async def __call__(self, handler, event, data):
        user_id = event.message.sender.user_id
        print(f"[AUDIT] попытка admin-flow от user_id={user_id}")
        return await handler(event, data)


class BroadcastLockMiddleware(BaseMiddleware):
    """Inner-router: захватывает lock только перед реальным broadcast.

    Регистрируется как inner, чтобы дорогая операция с Redis/etcd
    происходила исключительно когда handler будет вызван. Если IsAdmin
    отклонил запрос — lock не захватывается.
    """

    async def __call__(self, handler, event, data):
        # async with redis_lock("broadcast"):  ← настоящий lock
        print("→ broadcast lock захвачен")
        result = await handler(event, data)
        print("← broadcast lock освобождён")
        return result


# ── Роутеры и обработчики ────────────────────────────────────────────────────

admin_router = Router(router_id="admin")

admin_router.register_outer_middleware(AdminAccessLogMiddleware())
admin_router.register_inner_middleware(BroadcastLockMiddleware())


@admin_router.message_created(IsAdmin(), Command("broadcast"))
async def handle_broadcast(event: MessageCreated):
    await event.message.answer("Рассылка запущена!")


fallback_router = Router(router_id="fallback")


@fallback_router.message_created()
async def handle_fallback(event: MessageCreated):
    await event.message.answer("Привет! Введите /broadcast (если вы admin).")


# ── Сборка ───────────────────────────────────────────────────────────────────

dp = Dispatcher()

dp.register_outer_middleware(RequestIdMiddleware())
dp.register_inner_middleware(DbTransactionMiddleware())

dp.include_routers(admin_router, fallback_router)
```

### Что срабатывает в каждом сценарии

| Событие | Request<br>Id | Admin<br>AccessLog | Db<br>Transaction | Broadcast<br>Lock | handler |
|---|:-:|:-:|:-:|:-:|:-:|
| Сообщение от не-админа (не `/broadcast`) | ✅ | ✅¹ | ✅ | ❌ | `fallback` |
| `/broadcast` от не-админа | ✅ | ✅¹ | ✅ | ❌ | `fallback` |
| `/broadcast` от админа | ✅ | ✅ | ✅ | ✅ | `broadcast` |

¹ `AdminAccessLogMiddleware` — outer на `admin_router`, поэтому он
срабатывает для любого `MessageCreated`, дошедшего до этого роутера,
ещё до handler-фильтров (`IsAdmin`, `Command`). Если outer-middleware
должен логировать только `/broadcast`, такую проверку нужно делать
внутри него самого или вынести на уровень router-level фильтра.

### Порядок вызовов при успешном broadcast

```
dp.register_outer_middleware   → RequestIdMiddleware
  └── admin_router.outer_mw   → AdminAccessLogMiddleware
      └── [IsAdmin ✅, Command ✅]
          └── dp.inner_mw     → DbTransactionMiddleware
              └── router.inner_mw → BroadcastLockMiddleware
                  └── handle_broadcast()
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

## Перехват ошибок из обработчиков

Если внутри хендлера возникает исключение, диспетчер оборачивает его в
`HandlerException` и логирует. Middleware может перехватить это исключение
до логирования — поведение зависит от типа middleware.

### Outer middleware — получает `HandlerException`

```python
from maxapi.exceptions.dispatcher import HandlerException
from maxapi.filters.middleware import BaseMiddleware


class ErrorHandlerMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            await handler(event, data)
        except HandlerException as e:
            # e.cause — оригинальное исключение из хендлера
            # e.handler_title — имя функции-обработчика
            print(f"Ошибка в {e.handler_title}: {e.cause}")
            raise  # обязательно re-raise, иначе см. примечание ниже


dp.register_outer_middleware(ErrorHandlerMiddleware())
```

### Inner middleware — получает оригинальное исключение

Inner middleware вызывается внутри хендлера, до оборачивания исключения,
поэтому получает исходный тип исключения:

```python
class RawErrorMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        try:
            await handler(event, data)
        except ValueError as e:
            # ValueError напрямую, без HandlerException
            print(f"Ошибка валидации: {e}")
            raise


@dp.message_created(Command("start"), RawErrorMiddleware())
async def start(event: MessageCreated):
    await event.message.answer("a" * 5000)  # поднимет ValueError
```

### Поведение по типам

| Тип middleware | Получает | Доступ к оригиналу |
|---|---|---|
| **Inner** (в декораторе хендлера) | RAW исключение | напрямую |
| **Router outer** | `HandlerException` | `e.cause` |
| **Global outer** | `HandlerException` | `e.cause` |

!!! warning "Не забывайте `raise` после обработки"
    Если outer middleware поглощает `HandlerException` без `raise`,
    диспетчер корректно определит событие как обработанное и не напишет
    лишнего в лог. Однако `handle()` не будет логировать ошибку — вся
    ответственность за уведомление об ошибке ложится на middleware.

## Обработчики ошибок

Для централизованной обработки исключений используйте `Dispatcher.errors`
или `Router.errors`. Такой обработчик вызывается после того, как ошибка
в хендлере или middleware была обёрнута диспетчером.

```python
from maxapi import Dispatcher, ErrorEvent
from maxapi.filters import ExceptionTypeFilter


dp = Dispatcher()


@dp.message_created()
async def handler(event):
    raise ValueError("Некорректные данные")


@dp.errors(ValueError)
async def value_error_handler(event: ErrorEvent):
    # event.exception — оригинальный ValueError
    await event.update.message.answer("Не удалось обработать сообщение")


@dp.errors(ExceptionTypeFilter(RuntimeError))
async def runtime_error_handler(event: ErrorEvent):
    ...
```

В декоратор можно передавать:

- классы исключений, например `ValueError` или `RuntimeError`;
- обычные `BaseFilter`, включая `ExceptionTypeFilter`;
- `MagicFilter` через `F`, например `F.exception.args == ("boom",)`.

Если фильтр возвращает `dict`, данные передаются в error handler так же,
как в обычных обработчиках:

```python
from maxapi import ErrorEvent
from maxapi.filters import BaseFilter


class ErrorTextFilter(BaseFilter):
    async def __call__(self, event: ErrorEvent) -> dict[str, str]:
        return {"error_text": str(event.exception)}


@dp.errors(ValueError, ErrorTextFilter())
async def log_error(event: ErrorEvent, error_text: str):
    print(error_text)
```

`ErrorEvent` содержит:

- `update` — исходное событие;
- `exception` — оригинальное исключение;
- `handler_exception` — `HandlerException`, если упал handler;
- `middleware_exception` — `MiddlewareException`, если упала middleware;
- `context` и `raw_state` — FSM-контекст и состояние на момент ошибки;
- `router_id` и `process_info` — диагностическая информация диспетчера.

### Ошибки роутеров

`Router.errors` обрабатывает ошибки только своих обработчиков. Если
подходящий обработчик ошибки на роутере не найден, диспетчер пробует
глобальные обработчики `Dispatcher.errors`.

```python
from maxapi import Dispatcher, Router, ErrorEvent


dp = Dispatcher()
admin_router = Router("admin")


@admin_router.message_created()
async def admin_handler(event):
    raise PermissionError("forbidden")


@admin_router.errors(PermissionError)
async def admin_error(event: ErrorEvent):
    await event.update.message.answer("Недостаточно прав")


@dp.errors(Exception)
async def fallback_error(event: ErrorEvent):
    print(f"Необработанная ошибка: {event.exception}")


dp.include_routers(admin_router)
```

У `Dispatcher` также есть алиас `error`, поэтому
`dp.error.register(func, ValueError)` эквивалентен
`dp.errors.register(func, ValueError)`.

## Примеры использования

- Логирование
- Авторизация
- Обработка ошибок
- Измерение времени выполнения
- Модификация данных
