# AGENTS.md — MAX API

Async Python SDK + bot-фреймворк для мессенджера **MAX** (`https://platform-api.max.ru`). Стиль
вдохновлён aiogram: `Bot`, `Dispatcher`, `Router`, `F`, фильтры, middleware, FSM.

## Архитектура (что куда)

- `maxapi/bot.py` — `Bot(BaseConnection)`. Тонкие async-обёртки (`bot.send_message`,
  `bot.edit_chat`, …), каждая инстанцирует класс из `methods/` и делает `.fetch()`. Токен берётся
  из `MAX_BOT_TOKEN`, если не передан явно.
  `Bot.resolve_format/_resolve_notify/_resolve_disable_link_preview` сливают глобальные дефолты с
  per-call. Конструктор принимает дополнительные параметры загрузки медиа:
  `after_input_media_delay`, `after_upload_attempts`, `after_upload_retry_delay`,
  `after_upload_give_up_timeout`; настройки polling: `marker_updates`, `auto_check_subscriptions`;
  конфигурацию HTTP-соединения: `default_connection: DefaultConnectionProperties`.
- `maxapi/client/default.py` — `DefaultConnectionProperties`: настройки aiohttp-клиента (таймауты,
  `max_retries`, `retry_on_statuses`, `retry_backoff_factor`).
  Передаётся в `Bot(default_connection=DefaultConnectionProperties(...))`.
- `maxapi/methods/<verb>.py` — один класс на эндпоинт (`SendMessage`, `EditChat`, …). Конструктор
  валидирует/нормализует, `async def fetch()` собирает `params`/`json` и вызывает
  `super().request(method=HTTPMethod.X, path=ApiPath.Y, model=<PydanticResponse>, …)`. **Новый
  API-метод = новый файл здесь + проксирующий метод в `Bot` + типы ответа в `methods/types/`**. См.
  `methods/send_message.py` как канонический пример (включая retry на `attachment.not.ready`).
- `maxapi/connection/base.py` — `BaseConnection.request()`: единый HTTP-pipe c `aiohttp`,
  backoff-ретраями серверных 5xx и `ClientConnectionError`, парсингом ответа в pydantic-модель,
  выбросом `MaxApiError`/`InvalidToken`/`MaxConnection`. `download_file` — потоковое скачивание
  чанками `DOWNLOAD_CHUNK_SIZE=64KiB`.
- `maxapi/dispatcher.py` — `Dispatcher`/`Router` (Router = подкласс Dispatcher). Регистрация через
  `Event`-декораторы (`@dp.message_created(...)`, `@dp.bot_started()` …). `Dispatcher.handle()`
  строит **глобальный outer → роутерный outer → `_check_handler_match` → inner-цепочку (global
  inner + router inner + handler-level) → handler**. Два списка middleware: `outer_middlewares` (до
  проверки фильтров handler, на каждое событие) и `inner_middlewares` (только когда конкретный
  handler прошёл все фильтры). Регистрация: `dp.register_outer_middleware(mw)` /
  `dp.register_inner_middleware(mw)`. Старые `dp.middleware()` / `dp.outer_middleware()` —
  deprecated-алиасы. Inner-mw «выпекается» в `handler.mw_chain` при `_prepare_handlers()`.
  Цепочки и индекс `handlers_by_type: dict[UpdateType, list[Handler]]` кешируются при `__ready()`
  (`start_polling`/`startup`). Подробности и инварианты, включая router-scoped inner middleware —
  `doc/router_inner_middleware.md` (читать перед рефакторингом dispatcher/middleware).
- `maxapi/types/updates/` — pydantic-модели входящих событий, объединённые в `UpdateUnion`. После
  парсинга `utils/updates.py::enrich_event` через 3 хелпера (`_resolve_chat`, `_resolve_from_user`,
  `_inject_bot`) проставляет `event.chat`, `event.from_user`, `event.bot`. При
  `Bot(auto_requests=False)` тяжёлые поля остаются как `LazyRef`/`ChatRef`/`FromUserRef` (
  `types/fetchable.py`) — пользователь делает `await ref.fetch()` сам. Актуальные update-типы
  (помимо базовых): `dialog_cleared`, `dialog_muted`, `dialog_unmuted`, `dialog_removed`,
  `raw_api_response`, `on_started` (pseudo-тип для `startup`-callback); `message_chat_created`
  помечен deprecated с 0.9.14.
- `maxapi/filters/` — `BaseFilter` (async `__call__ → bool | dict`; возвращённый dict мёржится в
  kwargs хендлера), `BaseMiddleware` (`async __call__(handler, event, data)`), `Handler` (
  классифицирует переданные в декоратор `*args` по типу: `MagicFilter` → `filters`, `BaseFilter` →
  `base_filters`, `State`/`None` → `states`, `BaseMiddleware` → `middlewares`). `F = MagicFilter()`
  экспортируется из `maxapi`. Встроенные фильтры: `Command` / `CommandStart`
  (`filters/command.py`), `StateFilter` (`filters/state.py` — явная проверка FSM-state без
  параметра `states=`), `ChannelPostFilter` (`filters/channel_post.py` — фильтрует сообщения из
  каналов), `Contact`/`ContactFilter` (`filters/contact.py` — инжектирует
  `contact: ContactAttachment` в kwargs handler),
  `CallbackPayload`/`PayloadFilter` (`filters/callback_payload.py` — см. Patterns).
- `maxapi/context/` — `BaseContext` + `MemoryContext` (default, LRU 10_000 в `Dispatcher.contexts`)
  и `RedisContext`. Оба поддерживают `ttl: float | None` — истёкший TTL сбрасывает state и данные;
  реализован через `TTLTracker` (`context/ttl.py`). FSM: `State()` + `StatesGroup` в
  `state_machine.py` (имя автоматически `"Group:attr"`).
- `maxapi/webhook/` — `BaseMaxWebhook` + три бэкенда: `aiohttp.py` (default, в основной
  зависимости), `fastapi.py`, `litestar.py` (опц. экстры `[fastapi]`/`[litestar]`). Все валидируют
  заголовок `X-Max-Bot-Api-Secret`, если в конструктор передан `secret`. Вход parsится
  `process_update_webhook`, диспатч идентичный polling.

## Workflows

- Окружение: `uv sync --all-groups` → `source .venv/bin/activate`. Python ≥ 3.10, target — 3.10.
  Менеджер — **uv**, не pip/poetry.
- **Git — всегда с `--no-pager`** или через перенаправление (`| cat`), чтобы пагинатор не
  подвешивал выполнение: `git --no-pager log`, `git --no-pager diff`, `git --no-pager branch`, и
  т.д.
- Полная проверка перед PR: `make run-test` — параллельно запускает `ruff check .`,
  `ruff format . --check`, `mypy maxapi`, `pytest -q`. Форматирование — `make format`.
- Тесты: `pytest -q [tests/test_X.py]`. `asyncio_mode = "auto"` — async-тесты не нуждаются в
  декораторах. Маркер `@pytest.mark.integration` автоматически пропускается без `MAX_BOT_TOKEN` в
  env (см. `tests/conftest.py::pytest_collection_modifyitems`). Фикстуры событий —
  `tests/fixtures/updates.py`, параметризованная `update` покрывает все `UpdateType`. `.env`
  подхватывается автоматически.
- Документация: MkDocs Material (`mkdocs.yml`, `docs/`), генерится из docstring через
  `mkdocstrings[python]`.
- Каноничные сценарии использования — `examples/<NN>_*.py` (echo, formatting, keyboard, FSM,
  media, admin, router, middleware, webhook, callback_payload).

## Design philosophy

- **Совместимость с паттернами aiogram**: для максимального упрощения жизни пользователей,
  переходящих с aiogram, придерживайтесь его паттернов там, где это не противоречит особенностям
  MAX API и не является антипаттерном. Это касается именования методов, сигнатур middleware,
  структуры фильтров, FSM-интерфейса и т.д. При расхождении — документируйте решение явно.

## Project conventions

- **Язык docstring — русский**, формат — PEP 257, `"""…"""` обязательны на публичных
  модулях/классах/функциях как соглашение проекта. Актуальные автоматические проверки смотрите в
  `pyproject.toml`, дополнительные рекомендации по разработке — в `doc/dev.md`. Длина строки
  **79** (`pyproject.toml::tool.ruff`), docstring — 72.
- **Типы в секциях `Args`/`Attributes`/`Returns` не дублируем** — mkdocstrings читает их из
  аннотаций Python. Пишем только имя и описание: `name: Описание.`, но не `name (type): Описание.`
- `ruff` сконфигурён с `select = ["ALL"]` и широким `ignore`. Смотри `pyproject.toml` перед
  добавлением `# noqa` — многие категории (D, ANN, COM, EM, …) уже отключены глобально.
- Все runtime-импорты внутри пакета — **относительные** (`from ..enums.api_path import ApiPath`).
  Импорты только для типизации — под `if TYPE_CHECKING:` + `from __future__ import annotations`.
- Параметры с дефолтами на стороне `Bot` (`format`, `notify`, `disable_link_preview`) **не
  передавайте напрямую** в методы — резолвьте через `bot.resolve_format(...)`/
  `bot._resolve_notify(...)`. `parse_mode` помечен Deprecated, новые места — только
  `format: TextFormat`.
- Устаревшее API не удаляем молча: `warnings.warn(..., DeprecationWarning, stacklevel=2|3)` (см.
  `bot.change_info`, `Dispatcher.init_serve`, `Event.register` для deprecated update-типов).
- Ошибки бизнес-уровня — наследники `MaxApiError`/`InvalidToken`/`MaxConnection` из
  `exceptions/max.py`; диспетчерные — `HandlerException`/`MiddlewareException` из
  `exceptions/dispatcher.py` (всегда оборачивают исходное `cause=e` и кладут снапшот FSM
  `memory_context`).
- Логирование — именованные логгеры `logger_bot`/`logger_dp` из `maxapi/loggers.py`, **не**
  `logging.getLogger(__name__)` в коде SDK.
- Опциональная параллельная обработка событий — `Dispatcher(use_create_task=True)`; задачи держатся
  в `_background_tasks` (без этого GC может потерять task). `stop_polling()` дожидается их
  `asyncio.gather`.

## Patterns to follow

- Регистрация хендлера:
  `@dp.message_created(Command("start"), F.message.body.text == "ok", states=MyFSM.waiting)` —
  порядок аргументов произвольный, тип определяется в `filters/handler.py::Handler.__init__`.
- Высокоуровневые шорткаты на самих типах: `await event.message.answer("...")`,
  `await event.bot.send_message(...)` (см. `types/shortcuts.py`, `types/bot_mixin.py` — bot
  инжектится в `enrich_event`).
- Регистрация нового update-типа: модель в `types/updates/`, добавить в `UpdateUnion`, в
  `enums/update.py`, обработать в `utils/updates.py::_resolve_chat`/`_resolve_from_user`, добавить
  `Event` в `Dispatcher.__init__`, добавить фикстуру в `tests/fixtures/` и запись в
  `_FIXTURE_NAME_BY_UPDATE` в `tests/conftest.py` (иначе `test_fixtures_update_mapping.py` упадёт —
  это by design).
- Typed callback payload: наследуйтесь от `CallbackPayload` (pydantic-модель) с `prefix`/`separator`
  Class-vars. `instance.pack()` → строка ≤ 1024 байт; `MyPayload.unpack(str)` → объект.
  `MyPayload.filter(rule)` возвращает `PayloadFilter`, вставляемый в декоратор хендлера —
  совпавший payload инжектируется как `payload: MyPayload` в kwargs handler.
- Middleware: используйте `dp.register_outer_middleware(mw)` (outer — до фильтров handler) /
  `dp.register_inner_middleware(mw)` (inner — только когда handler реально вызван). То же на
  `router`. Старые `dp.middleware()` / `dp.outer_middleware()` / `router.middleware()` /
  `router.outer_middleware()` дают `DeprecationWarning`.
