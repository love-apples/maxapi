# Deep Linking

::: maxapi.utils.deep_linking

## Пример

```python
from maxapi import F, Router
from maxapi.types import BotStarted
from maxapi.utils.deep_linking import (
    create_start_link,
    decode_payload,
)

router = Router()

link = create_start_link("MyBot", "123456789", encode=True)


@router.bot_started(F.payload)
async def on_deep_link(event: BotStarted) -> None:
    user_id = decode_payload(event.payload)
```

В MAX payload из ссылки `https://max.ru/<botName>?start=<payload>`
приходит в событие `BotStarted.payload`.
