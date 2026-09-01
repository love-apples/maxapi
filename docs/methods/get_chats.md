# GetChats

!!! warning "Устарело"
    Начиная с июня 2026 года метод `GET /chats` больше не поддерживается —
    подробности на [странице метода в официальной документации
    MAX](https://dev.max.ru/docs-api/methods/GET/chats).

    Рекомендуемая замена — подписаться на события через
    [`subscribe_webhook()`](subscribe_webhook.md), указав в `update_types`
    [`bot_added`](../types/updates/bot_added.md),
    [`bot_started`](../types/updates/bot_started.md) и
    [`bot_removed`](../types/updates/bot_removed.md), и вести список
    `chat_id` самостоятельно: сохранять его при получении `bot_added`/
    `bot_started` (учитывая возможные дубли) и удалять по `bot_removed`.
    Накопленные `chat_id` используются в остальных методах API.

::: maxapi.methods.get_chats
    options:
      show_root_heading: false
      members_order: source
