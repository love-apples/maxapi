# Default Connection Properties

::: maxapi.client.DefaultConnectionProperties
    options:
      show_root_heading: false
      members_order: source

## Повторы запросов

`request()` повторяет запрос при `ClientConnectionError` и статусах из
`retry_on_statuses` (по умолчанию `502, 503, 504`). Превышение лимита
запросов (429) по умолчанию **не** повторяется и сразу поднимает
`MaxApiError(code=429)`. Чтобы повторять и его, добавьте статус явно:

```python
from maxapi import Bot
from maxapi.client import DefaultConnectionProperties

bot = Bot(
    token="...",
    default_connection=DefaultConnectionProperties(
        retry_on_statuses=(429, 502, 503, 504),
    ),
)
```

Задержка между попытками случайна в диапазоне от 0 до
`retry_backoff_factor * 2**n` (full jitter): при значении по умолчанию
1.0 верхние границы — 1, 2 и 4 с. Заголовок `Retry-After` не
учитывается: API MAX его не присылает. Ответ 429 выглядит так:
`{"code": "too.many.requests", "message": "Too many requests. Limit is:
10 calls per second."}`.

Колбэк `on_retry` вызывается перед каждым повтором и получает
`RetryEvent`. Он может быть синхронным или асинхронным. Возврат `False`
отменяет повтор: ошибка сразу уходит вызывающему коду. Исключение,
поднятое в колбэке, пробрасывается из `request()` как есть.

```python
from maxapi.client import DefaultConnectionProperties, RetryEvent


async def on_retry(event: RetryEvent) -> bool | None:
    if event.status == 429:
        await my_rate_limiter.pause(event.delay)
    return None  # продолжить повтор


conn = DefaultConnectionProperties(
    retry_on_statuses=(429, 502, 503, 504),
    on_retry=on_retry,
)
```

::: maxapi.client.RetryEvent
    options:
      show_root_heading: true

::: maxapi.client.default.RetryCallback
    options:
      show_root_heading: true
