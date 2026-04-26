# 📐 Предложение: явная пара `outer_middleware` / `inner_middleware` на всех уровнях

## Постановка проблемы

В текущей архитектуре `Dispatcher` middleware на уровне роутера
(`router.middleware()`) срабатывает **до** проверки state и handler-level
фильтров конкретного обработчика. Это создаёт класс побочных эффектов,
которые трудно предотвратить без дублирования кода.

### Конкретный сценарий

```python
admin_router = Router(router_id="admin")
admin_router.middleware(BroadcastLockMiddleware())   # хочется: lock только когда broadcast реально начнётся

@admin_router.message_created(IsAdmin(), Command("broadcast"))
async def handle_broadcast(event): ...

fallback_router = Router(router_id="fallback")

@fallback_router.message_created()
async def handle_fallback(event): ...

dp.include_routers(admin_router, fallback_router)
```

Не-админ пишет произвольное сообщение (фильтр `IsAdmin` его не пропустит).

**Текущий поток**:
```
_iter_and_dispatch_routers
├── admin_router:
│   ├── router filters: OK
│   ├── matching_handlers by update_type: [handle_broadcast]  — есть!
│   └── _dispatch_to_router:
│       └── admin_router.middleware chain → BroadcastLockMiddleware.__call__()  ← ВЫЗВАН
│           └── _invoke_router_handlers
│               └── _check_handler_match: IsAdmin → False → skip
│           _handled = False
│       admin_router вернул False → продолжаем
└── fallback_router:
    └── handle_fallback → выполнен
```

`BroadcastLockMiddleware` **отработала** — захватила распределённый lock
в Redis, открыла «pre-broadcast» состояние, может быть сообщила метрику
«broadcast attempted» — хотя реальный `handle_broadcast` так и не был
вызван. Любое сообщение в чате с админ-роутером триггерит дорогую
no-op'у lock-логики.

---

## Текущие уровни middleware (краткий recap)

| Уровень | Регистрация | Когда вызывается |
|---|---|---|
| **Глобальный** | `dp.middleware(mw)` | Для каждого события, до выбора роутера |
| **Роутерный (outer)** | `router.middleware(mw)` | После router-filters + наличия handler по `update_type`, но до проверки state/handler-filters |
| **Хендлерный** | `@router.event(mw, ...)` | Строго после `_check_handler_match` — state и все фильтры хендлера прошли |

Роутерный уровень ведёт себя как **outer**: входит до того, как известно,
какой конкретно handler будет вызван. Хендлерный уровень — строгий
**inner**, но требует аннотировать каждый обработчик отдельно.

### Gap

1. **Нет router-scoped inner middleware**: middleware, которая
   регистрируется один раз на роутер, но вызывается только тогда, когда
   конкретный handler из этого роутера фактически прошёл все свои
   фильтры и будет исполнен.

2. **Нет global-scoped inner middleware**: на уровне `Dispatcher` тоже
   нет способа сказать «вызывай эту mw только когда какой-то handler в
   итоге будет запущен». Сейчас `dp.middleware(mw)` всегда срабатывает
   на каждое событие — даже на те, что в итоге будут проигнорированы.
   Это полезно для логирования, но мешает для вещей с побочными
   эффектами (регистрация пользователя только при реальном
   взаимодействии, метрика только по «полезным» событиям и т. п.).

3. **Имя `middleware()` без квалификатора неоднозначно**. На роутере оно
   фактически означает outer, на диспетчере — тоже outer (по поведению),
   но в aiogram `middleware()` означает inner. Любой пользователь,
   переходящий с aiogram (или просто читающий код), вынужден помнить
   локальное соглашение.

   > **Примечательно**: в оригинальном коде `Dispatcher` уже существовал
   > метод `outer_middleware()` — он вставлял mw в *начало* списка
   > (`insert(0, ...)`), в отличие от `middleware()`, который добавлял в
   > конец (`append`).
   >
   > При этом «outer» у авторов означал **позицию обёртки внутри одного
   > списка middleware**: т.к. `build_middleware_chain` идёт по
   > `reversed(...)`, первый элемент списка оказывается самым внешним
   > слоем. Поэтому `insert(0, ...)` буквально читается как «обернуть
   > снаружи всех уже зарегистрированных». Это **другая ось**, чем
   > aiogram'овская «outer = до фильтров handler / inner = после».
   >
   > К счастью, обе интерпретации совпадают **по поведению**: всё, что
   > лежит в `outer_middlewares`, выполняется до проверки handler-фильтров
   > (потому что весь outer-список целиком обрамляет фазу выбора и
   > вызова handler). Поэтому наше переименование `outer_middleware()`
   > → `register_outer_middleware()` остаётся корректным сразу в обоих
   > смыслах: и в авторском (позиция обёртки), и в нашем расширенном
   > (timing относительно фильтров). Симметричный термин `inner` теперь
   > занимает свободное место — «то, что выполняется *после* того, как
   > handler уже выбран».

Финальное направление — сделать у нас явную пару `outer` / `inner`
**на всех трёх уровнях** (более очевидную, чем aiogram, где безымянный
`middleware()` означает inner):

| Уровень | aiogram | maxapi (после) |
|---|---|---|
| Глобальный outer | `dp.update.outer_middleware` | `dp.outer_middleware` |
| Глобальный inner | `dp.update.middleware` | `dp.inner_middleware` ✨ |
| Роутерный outer | `router.update.outer_middleware` | `router.outer_middleware` |
| Роутерный inner | `router.update.middleware` | `router.inner_middleware` ✨ |
| Безымянный alias | — | `dp.middleware` / `router.middleware` (deprecated → outer) |
| Уже существовавший alias | — | `dp.outer_middleware()` / `router.outer_middleware()` (deprecated → `register_outer_middleware`) |

---

## Предлагаемое решение

Сделать **на каждом уровне** (диспетчер и роутер) явную пару методов:

| Метод | Семантика | Старт цепочки |
|---|---|---|
| `dp.register_outer_middleware(mw)` | глобальный outer | до выбора роутера |
| `dp.register_inner_middleware(mw)` ✨ | глобальный inner | только если какой-то handler выбран |
| `router.register_outer_middleware(mw)` | роутерный outer | после router-filters + есть handler по `update_type` |
| `router.register_inner_middleware(mw)` ✨ | роутерный inner | только когда конкретный handler этого роутера прошёл `_check_handler_match` |

И deprecated-алиасы безымянных методов:

- `dp.middleware(mw)` → deprecated alias на `dp.register_outer_middleware(mw)`;
- `router.middleware(mw)` → deprecated alias на `router.register_outer_middleware(mw)`.

Поведение алиасов **полностью сохраняется**, добавляется только
`DeprecationWarning` со ссылкой на новые методы.

### Реализация: «выпекание» в `handler.mw_chain`

Все inner-уровни (глобальный + накопленные роутерные) при `__ready()`
встраиваются в `handler.mw_chain` каждого обработчика. В горячем пути
ничего не меняется.

```
handler.mw_chain =
    dp.inner_middlewares                      ← глобальный inner
  + accumulated_router_inner_middlewares      ← inner всех роутеров-предков + текущего
  + handler.middlewares                       ← handler-level (как сейчас)
  → call_handler
```

Цепочка `dp` outer + router outer остаётся ровно такой, как сейчас.

### Ключевая идея

`handler.mw_chain` уже строится один раз при `_prepare_handlers` и
хранится в кеше. Сейчас цепочка выглядит так:

```
handler.mw_chain = handler.middlewares → call_handler
```

После изменения:

```
handler.mw_chain = accumulated_inner_middlewares + handler.middlewares → call_handler
```

Где `accumulated_inner_middlewares` — список inner-middleware, накопленный
рекурсивно от всех родительских роутеров до данного (та же логика
накопления, что сейчас у `router.middlewares`).

---

## Детали реализации

### 1. `Dispatcher.__init__` — переименование и новый атрибут

```python
self.outer_middlewares: list[BaseMiddleware] = []   # было: self.middlewares
self.inner_middlewares: list[BaseMiddleware] = []   # новый
```

Атрибут `middlewares` сохраняется как `@property`-алиас с
`DeprecationWarning` — прямой доступ к нему продолжает работать:

```python
@property
def middlewares(self) -> list[BaseMiddleware]:
    """
    .. deprecated::
        Используйте :attr:`outer_middlewares`.
    """
    warnings.warn(
        f"{type(self).__name__}.middlewares устарел. "
        "Используйте outer_middlewares.",
        DeprecationWarning,
        stacklevel=2,
    )
    return self.outer_middlewares
```

Это значит, что существующий код вида `router.middlewares` продолжает
читать и модифицировать правильный список — только с предупреждением.

(Оба атрибута определяются в `Dispatcher` и наследуются `Router`.)

### 2. Методы регистрации (одинаковы для `Dispatcher` и `Router`)

```python
def register_outer_middleware(self, middleware: BaseMiddleware) -> None:
    """Outer middleware (до фильтров handler).

    Использует ``append``: первый зарегистрированный mw — самый
    внешний слой цепочки (register order = execution order).
    Симметрично с :meth:`register_inner_middleware`.
    """
    self.outer_middlewares.append(middleware)

def register_inner_middleware(self, middleware: BaseMiddleware) -> None:
    """Inner middleware (после фильтров handler).

    Вызывается только когда конкретный handler прошёл state и filters
    и будет реально исполнен. На уровне Dispatcher это означает «mw
    срабатывает только для событий, реально попавших в какой-то
    handler»; на уровне Router — то же, но только для своих handlers.
    """
    self.inner_middlewares.append(middleware)

def register_middleware(self, middleware: BaseMiddleware) -> None:
    """
    .. deprecated::
        Используйте :meth:`register_outer_middleware` (если нужно текущее
        поведение «до фильтров handler») или :meth:`register_inner_middleware`
        (если нужно «только когда handler реально вызван»).
    """
    warnings.warn(
        f"{type(self).__name__}.middleware() помечен deprecated. "
        "Используйте register_outer_middleware() (поведение сохраняется) "
        "или register_inner_middleware() для запуска mw после фильтров handler.",
        DeprecationWarning,
        stacklevel=2,
    )
    self.outer_middlewares.append(middleware)
```

> Примечание: метод `middleware()` (deprecated alias) исторически делал
> `append`, а `outer_middleware()` (тоже deprecated) — `insert(0, ...)`.
> Новый `register_outer_middleware()` использует `append`, как и
> `register_inner_middleware()`: «register order = execution order».
> Старые алиасы сохраняют свои исторические append/insert(0) — чтобы
> существующий пользовательский код не получил тихого изменения порядка.

### 3. `_iter_routers` — накопление inner_middlewares

Сигнатура расширяется аналогично текущим `parent_middlewares`:

```python
def _iter_routers(
    self,
    routers,
    parent_middlewares=None,
    parent_inner_middlewares=None,   # новый параметр
    parent_filters=None,
    parent_base_filters=None,
    path=None,
) -> Iterator[tuple[Router, list, list, list, list]]:  # 5-й элемент — inner_mw
    ...
    if router is self:
        accumulated_middlewares = middlewares
    else:
        accumulated_middlewares = middlewares + router.outer_middlewares

    if router is self:
        accumulated_inner_middlewares = inner_middlewares
    else:
        accumulated_inner_middlewares = inner_middlewares + router.inner_middlewares

    yield (
        router,
        accumulated_middlewares,
        accumulated_inner_middlewares,   # ← новый 5-й элемент
        accumulated_filters,
        accumulated_base_filters,
    )
```

> **Важно**: внутри SDK все обращения к списку outer-mw используют
> `router.outer_middlewares` напрямую — это позволяет избежать лишних
> `DeprecationWarning` из внутреннего кода. Алиас `router.middlewares`
> предназначен только для внешнего пользовательского кода.

### 4. `_prepare_handlers` — встраивание inner-middleware в handler.mw_chain

```python
def _prepare_handlers(self, bot: Bot) -> None:
    # Глобальный inner-уровень — общий для всех handlers независимо
    # от роутера, в который они зарегистрированы.
    global_inner_mw = self.inner_middlewares

    for router, _, accumulated_inner_mw, *_ in self._iter_unique_routers(
        self.routers, warn_duplicates=True
    ):
        router.bot = bot
        router.handlers_by_type = {}

        for handler in router.event_handlers:
            extract_commands(handler, bot)
            handler.func_args = frozenset(handler.func_event.__annotations__)

            # Порядок: global inner → router inner (накопленный) → handler mw
            # Внешний слой — global, внутренний — handler.
            all_inner = (
                global_inner_mw
                + accumulated_inner_mw
                + handler.middlewares
            )
            handler.mw_chain = self.build_middleware_chain(
                all_inner,
                functools.partial(self.call_handler, handler),
            )
            router.handlers_by_type.setdefault(
                handler.update_type, []
            ).append(handler)

    self._cached_router_entries = list(self._iter_unique_routers(self.routers))
```

Обратите внимание: `_cached_router_entries` хранит `(router,
outer_middlewares, inner_middlewares, filters, base_filters)` — пятый
элемент добавляется, но **не используется в горячем пути
`_iter_and_dispatch_routers`**, потому что inner_mw уже выпечена в
`handler.mw_chain`. Если `_cached_router_entries` используется только для
горячего пути, можно оставить формат прежним (4 элемента) и хранить
inner отдельно только на этапе `_prepare_handlers`.

> Важно: `accumulated_inner_mw` для `router is self` пуст, потому что
> `_iter_routers` для `self` не добавляет его в накопление (та же логика,
> что для outer). Глобальный inner-уровень добавляется явно из
> `self.inner_middlewares`, не через `_iter_routers`. Это убирает
> двойное добавление, когда обработчик зарегистрирован прямо на `dp`.

---

## Поток вызовов после изменения

```
handle()
└── _global_mw_chain (dp.outer_middlewares)        ← global outer: для каждого события
     └── _process_event
          └── _iter_and_dispatch_routers
               ├── admin_router:
               │   └── _dispatch_to_router
               │       └── admin_router.outer_mw chain  ← router outer: ДО handler-filters
               │           └── _invoke_router_handlers
               │               └── _run_router_handlers
               │                   └── _check_handler_match    ← state + filters (incl. IsAdmin)
               │                       └── _execute_handler
               │                           └── handler.mw_chain:
               │                               dp.inner_mw            ← global inner
               │                               admin_router.inner_mw  ← router inner
               │                               handler.mw             ← handler-level
               │                               call_handler
               └── fallback_router: (аналогично)
```

То есть **outer-цепочка строится сверху вниз** (`global_outer →
router_outer`), а **inner-цепочка — внутри `handler.mw_chain` от global
inner к handler-level**. Все они выполняются **только если
`_check_handler_match` пройден** — иначе мы туда даже не входим.

Сценарий из раздела «Постановка проблемы» теперь работает корректно:

```
admin_router:
  router filters: OK
  matching_handlers by update_type: [handle_broadcast]
  _dispatch_to_router:
    admin_router.outer_mw: нет (пусто)
    _check_handler_match: IsAdmin → False → skip
    _handled = False → продолжаем

fallback_router:
  handle_fallback → выполнен
```

`BroadcastLockMiddleware`, зарегистрированная через
`admin_router.register_inner_middleware()`, не вызывается — потому что не
вызывается `handle_broadcast`. Lock в Redis не захватывается
вхолостую.

---

## Влияние на кеширование

Вся логика inner_middleware **выпекается при `__ready()`** в
`_prepare_handlers`. В горячем пути (`handle()` → `_iter_and_dispatch_routers`
→ `_dispatch_to_router`) нет ни одного нового вычисления — `handler.mw_chain`
уже содержит все слои.

Текущий кеш `_cached_router_entries` не меняет свою роль:
он хранит `outer_middlewares` для построения router-level outer-chain.

### Overhead изменения

| Метрика | До | После |
|---|---|---|
| Аллокаций в горячем пути | 0 | 0 (без изменений) |
| Построений `handler.mw_chain` | 1× при `__ready` | 1× при `__ready` |
| Размер `handler.mw_chain` | `len(handler.mw)` слоёв | `len(inner_mw) + len(handler.mw)` слоёв |
| Изменений в `_iter_and_dispatch_routers` | — | нет |

---

## Обратная совместимость

- **`dp.middleware()` / `router.middleware()`** — поведение не меняется,
  добавляется только `DeprecationWarning` со ссылкой на
  `register_outer_middleware()` / `register_inner_middleware()`. Существующий код
  продолжает работать.
- **`dp.outer_middleware()` / `router.outer_middleware()`** — этот метод
  существовал в оригинальном коде до нашего изменения (вставлял mw первым
  через `insert(0, ...)`). Сохранён как deprecated-алиас с
  `DeprecationWarning`, поведение `insert(0, ...)` не меняется — чтобы
  существующий код не получил тихого изменения порядка регистрации.
  Новый `register_outer_middleware()` использует `append`.
- **`dp.register_outer_middleware()` / `router.register_outer_middleware()`** —
  использует `append` (первый зарегистрированный mw — самый внешний
  слой). Это **отличается** от исторического `outer_middleware()`
  (`insert(0, ...)`); см. таблицу выше. Симметрично с
  `register_inner_middleware()`.
- **`_global_mw_chain`** — продолжает строиться из `self.outer_middlewares`
  (переименован из `self.middlewares`). Никаких изменений в горячем пути
  `handle()`.
- **`handler.mw_chain`** — если `dp.inner_middlewares` и
  `router.inner_middlewares` пусты (по умолчанию), построение идёт по
  прежнему пути: `handler.middlewares → call_handler`. Нулевые списки не
  добавляют слоёв.
- **`router.middlewares`** → становится `@property`-алиасом на
  `router.outer_middlewares` с `DeprecationWarning`. Чтение, запись
  через `.append()` / `.insert()` и итерация — всё продолжает работать
  без изменений поведения. Никакого тихого breaking change.
- **Новый public API**: `dp.register_inner_middleware(mw)`,
  `router.register_inner_middleware(mw)`. Реализованы один раз в базовом классе
  `Dispatcher` и автоматически наследуются `Router`.

---

## Пример использования

```python
from maxapi import Router, Dispatcher, Bot
from myapp.middleware import (
    RequestIdMiddleware, LoggingMiddleware,
    DbTransactionMiddleware, HandlerLatencyMetricMiddleware,
    AdminAccessLogMiddleware, BroadcastLockMiddleware,
)
from myapp.filters import IsAdmin
from maxapi.filters import Command

dp = Dispatcher()

# ─── Глобальный outer ─────────────────────────────────────────────
# Срабатывает для каждого события, даже для тех, что в итоге будут
# проигнорированы. Подходит всё, что должно «жить» в контексте
# любого входящего апдейта.
dp.register_outer_middleware(RequestIdMiddleware())   # request_id для трейсинга
dp.register_outer_middleware(LoggingMiddleware())     # лог всех updates

# ─── Глобальный inner ─────────────────────────────────────────────
# Срабатывает только если какой-то handler реально будет выполнен.
# Подходит то, что бессмысленно делать «вхолостую».
dp.register_inner_middleware(DbTransactionMiddleware())          # транзакция только под handler
dp.register_inner_middleware(HandlerLatencyMetricMiddleware())   # метрика времени handler

admin_router = Router(router_id="admin")

# ─── Router outer ─────────────────────────────────────────────────
# Срабатывает для любых событий, попавших в admin_router по типу,
# даже если admin-filter их не пропустит. Здесь — security audit:
# нам важно знать о ЛЮБОЙ попытке нажать на admin-команду.
admin_router.register_outer_middleware(AdminAccessLogMiddleware())

# ─── Router inner ─────────────────────────────────────────────────
# Срабатывает только когда конкретный admin-handler реально вызван.
# Здесь — распределённый lock, который имеет смысл захватывать
# исключительно перед началом тяжёлой операции.
admin_router.register_inner_middleware(BroadcastLockMiddleware())

@admin_router.message_created(IsAdmin(), Command("broadcast"))
async def broadcast(event): ...

dp.include_routers(admin_router)
```

Что сработает в каждом сценарии:

| Событие | Request<br>Id | Logging | Admin<br>AccessLog | Db<br>Transaction | Latency<br>Metric | Broadcast<br>Lock | broadcast |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Случайное сообщение от не-админа | ✅ | ✅ | ✅¹ | ❌ | ❌ | ❌ | ❌ |
| `/broadcast` от не-админа (`IsAdmin` не пропустил) | ✅ | ✅ | ✅¹ | ❌ | ❌ | ❌ | ❌ |
| `/broadcast` от админа | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

¹ `AdminAccessLogMiddleware` — outer на роутере, поэтому фиксирует
**попытку** взаимодействия с admin-flow раньше, чем `IsAdmin` отсечёт
запрос. Ровно то, что нужно security-аудиту.

Контраст ролей:

- **`AdminAccessLogMiddleware` (outer)** — нам важно знать о ЛЮБОЙ
  попытке нажать админскую команду, в том числе неудачной. Если бы это
  была inner, мы бы записывали только успешные действия — и пропустили
  бы перебор подозрительных команд от не-админов.
- **`BroadcastLockMiddleware` (inner)** — захватывать distributed lock
  есть смысл только когда мы реально собираемся начать broadcast. Если
  бы это была outer, мы бы держали (и отпускали) lock на каждом
  сообщении в `admin_router`, что бессмысленно нагружает Redis/etcd.
- **`DbTransactionMiddleware` (global inner)** — открывать транзакцию
  для каждого update, который бот видит, дорого и в большинстве случаев
  не нужно. Inner гарантирует, что транзакция стартует только под
  реальный handler.
- **`LoggingMiddleware` (global outer)** — лог нужен на каждое событие,
  иначе при отладке «почему мой handler не вызвался» мы не увидим самого
  факта того, что update пришёл.

> **Миграция со старого `register_middleware()`** (на любом уровне): если нужно
> сохранить текущее поведение (mw до фильтров handler) — заменить на
> `register_outer_middleware()`. Если хочется получить семантику «mw только когда
> handler реально вызван» — заменить на `register_inner_middleware()`. После
> замены `DeprecationWarning` исчезнет.

---

## Наследование в дереве роутеров

Inner middleware накапливается по дереву так же, как сейчас накапливаются
outer middleware и фильтры:

```python
parent = Router(router_id="parent")
parent.register_inner_middleware(DbTransactionMiddleware())   # на любой handler в parent + детях

child = Router(router_id="child")
child.register_inner_middleware(ChildAuditMiddleware())       # только на handler внутри child
parent.include_routers(child)
```

Для хендлеров внутри `child`:
```
handler.mw_chain = [DbTransactionMiddleware, ChildAuditMiddleware] + handler.middlewares → call_handler
```

Для хендлеров напрямую в `parent`:
```
handler.mw_chain = [DbTransactionMiddleware] + handler.middlewares → call_handler
```

---

## Scope изменений

| Файл | Изменение |
|---|---|
| `maxapi/dispatcher.py` | `Dispatcher.__init__`: `middlewares` → `outer_middlewares` (реальный атрибут); `middlewares` остаётся как `@property`-алиас с `DeprecationWarning`; +`inner_middlewares = []`; `_iter_routers` / `_iter_unique_routers`: +5-й элемент (inner-mw), внутри используют `router.outer_middlewares`; `_prepare_handlers`: встраивает `dp.inner_middlewares + router.accumulated_inner_mw` в `handler.mw_chain`; +`register_inner_middleware()`; в `middleware()` — `DeprecationWarning`. `_global_mw_chain` строится из `self.outer_middlewares`. Все методы определяются один раз в `Dispatcher` и наследуются `Router`. |
| `tests/test_dispatcher.py` | Тесты: global inner вызывается только при handler match; global inner НЕ вызывается без handler; `DeprecationWarning` от `dp.middleware()` |
| `tests/test_nested_routers.py` | Параметризованные тесты для router inner: наследование, изоляция между роутерами, порядок выполнения относительно global inner и handler-mw |
| `docs/dispatcher.md` | Раздел про `outer_middleware` / `inner_middleware` на обоих уровнях; пометка `register_middleware()` как deprecated |
| `README.md`, `docs/examples.md` | Обновить примеры, использующие `dp.middleware()` / `router.middleware()` |
| `CHANGELOG` | Запись о новом API + deprecation |

Изменения в `_iter_and_dispatch_routers`, `_dispatch_to_router`,
`handle()` и `_global_mw_chain` — **нулевые**. Горячий путь не трогается.

---

## Что НЕ решает это изменение

- **«Middleware только если хоть один роутер обработал событие»** — это
  ровно то, что закрывает `dp.register_inner_middleware(mw)`. Дополнительных
  костылей с `data["_is_handled"]` больше не нужно.
- **Динамическая регистрация middleware после старта** — невозможна с
  кешированием; требует явного `dp.stop_polling()` + повторного старта.
  Это ограничение архитектуры, а не данного изменения.

---

## Сравнение с aiogram 3.x

### Архитектура aiogram

В aiogram middleware регистрируется **не на роутере целиком**, а на
конкретном `TelegramEventObserver` (наблюдателе одного типа события):

```python
# aiogram
router = Router()

router.message.outer_middleware(LoggingMiddleware())   # outer для message-обзёрвера
router.message.middleware(AuthMiddleware())            # inner для message-обзёрвера

router.callback_query.middleware(RateLimitMiddleware())  # только для callback_query

# Дополнительно: middleware на уровне Router.update — ловит ВСЕ типы
router.update.outer_middleware(TracingMiddleware())
```

То есть в aiogram middleware-уровней **больше**, чем у нас:

| Уровень | aiogram | maxapi (после предложения) |
|---|---|---|
| Глобальный | `Dispatcher.update.outer_middleware` | `dp.register_outer_middleware` |
| На Router (любой update) | `Router.update.outer_middleware` / `.middleware` | `router.register_outer_middleware` / `router.register_inner_middleware` |
| **Per-update-type на роутере** | `router.message.outer_middleware` / `.middleware` | *(отсутствует)* |
| На handler | через `flags`/декораторы | `@router.event(mw, ...)` |

### Поток вызовов в aiogram

```
Dispatcher.feed_update
└── Dispatcher.update.outer_middleware     (глобальный outer)
    └── Router.update.outer_middleware     (роутерный outer для любого типа)
        └── observer.outer_middleware      (outer для конкретного типа)
            └── Filters check              ← здесь решается, какой handler
                └── observer.middleware    (inner для конкретного типа)  ← после filters
                    └── Router.update.middleware   (inner на роутере)    ← после filters
                        └── handler(event, **data)
```

Ключевые особенности:

1. **`outer_middleware` явно отделён от `middleware`** на каждом уровне:
   outer вызывается до проверки фильтров, inner — после. Это **именно та
   семантика**, которую мы вводим, но aiogram применяет её
   последовательно к каждому уровню.
2. **Middleware регистрируется per-update-type** (`router.message.middleware`,
   `router.callback_query.middleware`) — более узкий scope, чем «на весь
   роутер сразу».
3. **`data: dict` накапливается через цепочку** — middleware может
   положить ключи в `data`, и они приедут в handler как kwargs (это у нас
   уже есть через `data.update(...)`, а затем `Dispatcher._execute_handler()`
   отбирает подходящие аргументы по `handler.func_args`/`__annotations__`).
4. **Цепочка строится динамически** — нет кеша, на каждое событие
   собирается заново через `_resolve_middlewares()`. Это **минус**
   aiogram (больше аллокаций), у нас здесь архитектурное преимущество.

### Что стоит заимствовать

#### 1. ✅ Терминологию `outer_middleware` / `middleware`

В aiogram:
- `middleware()` = **inner** (после фильтров)
- `outer_middleware()` = **outer** (до фильтров)

В maxapi сейчас:
- `middleware()` = **outer** (до фильтров handler)
- `outer_middleware()` = тот же outer, но в начало списка

Это **расхождение в семантике одинакового имени** между фреймворками
будет постоянно путать разработчиков, переходящих с aiogram. Конкретно
это видно из feedback автора PR #131:

> *«В aiogram для этого удобно, что есть явное разделение: outer
> middleware — до filters, обычная middleware — после filters»*

#### Финальное решение по именованию

Делаем явную пару `register_inner_middleware()` / `register_outer_middleware()` **на каждом
уровне** (диспетчер и роутер), а безымянный `register_middleware()` помечаем как
deprecated-alias на `register_outer_middleware()` (поведение не меняется, только
warning):

```python
# Глобальный уровень
dp.register_outer_middleware(LoggingMW())     # ✅ канонично: outer (для каждого события)
dp.register_inner_middleware(MetricsMW())     # ✅ канонично: inner (только когда handler сработал)
dp.middleware(SomeMW())              # ⚠️ DeprecationWarning → используйте .register_outer_middleware()

# Роутерный уровень
router.register_outer_middleware(TracingMW()) # ✅ канонично: outer (до filters handler)
router.register_inner_middleware(AuthMW())    # ✅ канонично: inner (после filters handler)
router.middleware(AuditMW())         # ⚠️ DeprecationWarning → используйте .register_outer_middleware()
```

**Почему это лучше aiogram**: в aiogram `router.middleware()` без
суффикса означает inner — это контринтуитивно (по логике «middleware =
обёртка вокруг чего-то», без квалификатора непонятно, вокруг чего).
В нашем варианте имя без суффикса вообще не используется в новом коде —
вместо него явная пара inner/outer на любом уровне. У читателя нет места
для догадок.

| | aiogram | maxapi (после) |
|---|---|---|
| outer global | `dp.update.outer_middleware()` | `dp.register_outer_middleware()` |
| inner global | `dp.update.middleware()` | `dp.register_inner_middleware()` ✨ явнее |
| outer router | `router.update.outer_middleware()` | `router.register_outer_middleware()` |
| inner router | `router.update.middleware()` | `router.register_inner_middleware()` ✨ явнее |
| безымянный alias | — | `dp.middleware()` / `router.middleware()` (deprecated на outer) |

##### Решение по порядку регистрации `register_outer_middleware()`

Исторический `outer_middleware()` делал `insert(0, ...)` — каждая
новая регистрация становилась самым внешним слоем. В авторской
ментальной модели это читалось как «обернуть снаружи всех уже
зарегистрированных» (см. примечание в разделе «Постановка проблемы»).

В новом `register_outer_middleware()` порядок изменён на `append`:
**первый зарегистрированный — самый внешний** (register order =
execution order). Причины:

- симметрично с `register_inner_middleware()`, который тоже `append`;
- интуитивно для большинства пользователей: «как написал, так и
  выполнится»;
- совпадает с поведением aiogram (`outer_middleware`/`middleware` там
  тоже append-based).

Старый deprecated-алиас `outer_middleware()` сохраняет исторический
`insert(0, ...)` — это позволяет существующему коду не получить
тихого breaking change. При миграции на `register_outer_middleware()`
порядок может перевернуться; deprecation-сообщение об этом
напоминает.

#### План deprecation (по версиям)

| Версия | Действие |
|---|---|
| `1.x` (текущий минор) | Добавить `register_inner_middleware()`. `register_middleware()` начинает выдавать `DeprecationWarning` со ссылкой на `register_outer_middleware()` / `register_inner_middleware()`. Поведение `register_middleware()` не меняется. |
| `1.x+1` | В `CHANGELOG` напомнить о deprecation. Обновить все примеры в `docs/` и `README` под новые имена. |
| `2.0` | Удалить `register_middleware()` как метод. Рассмотреть переименование `register_outer_middleware()` → оставить, привести в соответствие с `register_inner_middleware()`. |

Существующий код `router.middleware(mw)` продолжает работать всю серию
`1.x`, только с warning. Никакого breaking change в пределах минора.


#### 2. ⚠️ Per-update-type middleware — НЕ заимствовать сейчас

Идея `router.message.middleware(...)` требует архитектурного рефакторинга
под `EventObserver`. У нас сейчас `router.event_handlers: list[Handler]`
с `update_type` как полем — нет per-type объекта. Введение наблюдателей —
большое изменение, которое не оправдано до тех пор, пока на это нет
явного запроса.

**Альтернатива**: тот же эффект достигается **созданием отдельного
`Router` под каждый flow / тип событий**, что уже идиоматично:

```python
# вместо router.message.middleware(...)
message_router = Router()
message_router.register_inner_middleware(MyMW())

@message_router.message_created()
async def handler(event): ...
```

#### 3. ✅ Накопление `data` через цепочку — уже есть

Aiogram позволяет middleware класть ключи в `data: dict`, которые потом
доедут до handler как kwargs. У нас это тоже работает: middleware может
делать `data.update(...)`, а дальше `Dispatcher._execute_handler()`
передаст в handler только те kwargs, которые он реально принимает,
ориентируясь на `handler.func_args` / `__annotations__`.

Заимствовать ничего не нужно — паритет по факту достигнут.

#### 4. ❌ Динамическое построение цепочки — НЕ заимствовать

Aiogram пересобирает middleware-chain на каждое событие через
`_resolve_middlewares()`. У нас цепочки кешируются при `__ready()` —
см. п. 3 и п. 9 в `doc/dispatcher_optimization.md`. Это наше осознанное
преимущество, его нужно сохранить.

#### 5. ✅ Контракт `middleware(handler, event, data)` — уже идентичен

```python
# и aiogram, и maxapi:
class MyMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        # pre-handler
        result = await handler(event, data)
        # post-handler
        return result
```

Сигнатура совпадает один-в-один. Это плюс для пользователей, переходящих
с aiogram — middleware-классы переносятся почти без изменений.

### Итоговая таблица заимствований

| Из aiogram | Заимствовать? | Как |
|---|---|---|
| Терминология `outer` vs `inner` | ✅ Да, расширенно | Явная пара `register_outer_middleware()` + `register_inner_middleware()`. `register_middleware()` — deprecated alias на outer. Это даже **очевиднее, чем в aiogram**, где безымянный `middleware()` означает inner |
| Inner-семантика на роутере (после filters) | ✅ Да | Это и есть основное предложение |
| Накопление `data` в цепочке | ✅ Уже есть | Ничего не делать |
| Сигнатура `(handler, event, data)` | ✅ Уже есть | Ничего не делать |
| Per-update-type observer (`router.message.middleware`) | ❌ Нет | Решается через отдельные `Router` |
| Динамическая сборка цепочки на каждое событие | ❌ Нет | У нас лучше: кеш в `__ready` |
| Гибрид filter+middleware через `flags` | ❌ Нет | Не вписывается в нашу модель `BaseFilter`/`MagicFilter` |

### Вывод

Финальное предложение — явная пара `register_outer_middleware()` /
`register_inner_middleware()` **на каждом уровне** (`Dispatcher` и `Router`) +
deprecation безымянного `register_middleware()` в пользу этой пары. Это:

- **полностью покрывает gap**, ради которого пользователи aiogram
  пишут `router.message.middleware(...)` (router-scoped inner);
- **расширяет idea на глобальный уровень**: `dp.register_inner_middleware()`
  даёт «middleware только когда какой-то handler в итоге сработал» —
  семантику, которой в aiogram отдельно нет (там это смесь global
  outer + per-observer inner);
- **API получается очевиднее, чем в aiogram**: имя без квалификатора
  (`register_middleware()`) вообще не используется в новом коде, у читателя нет
  места для догадок, inner это или outer, и на каком уровне;
- **горячий путь не трогается**: вся inner-логика выпекается в
  `handler.mw_chain` при `__ready()`.

Заимствование per-observer-архитектуры aiogram
(`router.message.middleware(...)`) **не оправдано**: это объёмный
рефакторинг ради синтаксической косметики, который ломает текущую
модель регистрации хендлеров через `Event`-декораторы. Тот же эффект
достигается отдельным `Router` под каждый flow.
