# GetChats

!!! warning "Устарело"
    Начиная с июня 2026 года метод `GET /chats` больше не поддерживается
    — подробности на [странице метода в официальной документации
    MAX](https://dev.max.ru/docs-api/methods/GET/chats).

    Рекомендуемая замена — накапливать `chat_id` из событий
    [`bot_added`](../types/updates/bot_added.md),
    [`bot_started`](../types/updates/bot_started.md),
    [`bot_removed`](../types/updates/bot_removed.md) и
    [`bot_stopped`](../types/updates/bot_stopped.md) (Long Polling или
    [`subscribe_webhook()`](subscribe_webhook.md)): сохранять `chat_id`
    при `bot_added`/`bot_started`, удалять при `bot_removed` (для диалогов
    — при `bot_stopped`). Подробный сценарий — ниже в описании класса и в
    [руководстве по хендлерам](../guides/handlers.md#bot-events).

::: maxapi.methods.get_chats
    options:
      show_root_heading: false
      members_order: source
