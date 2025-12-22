# Клавиатуры

## InlineKeyboardBuilder

Рекомендуемый способ создания клавиатур:

```python
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.types.attachments.buttons import LinkButton, CallbackButton

builder = InlineKeyboardBuilder()
builder.row(
    LinkButton(text="Сайт", url="https://example.com"),
    CallbackButton(text="Нажми", payload="data"),
)
builder.row(CallbackButton(text="Ещё кнопка", payload="more"))

await event.message.answer(
    text="Выберите действие:",
    attachments=[builder.as_markup()]
)
```

## Через ButtonsPayload

Альтернативный способ:

```python
from maxapi.types.attachments.attachment import ButtonsPayload
from maxapi.types.attachments.buttons import LinkButton, CallbackButton

buttons = [
    [LinkButton(text="Сайт", url="https://example.com")],
    [CallbackButton(text="Callback", payload="data")]
]
payload = ButtonsPayload(buttons=buttons).pack()

await event.message.answer(
    text="Клавиатура",
    attachments=[payload]
)
```

## Типы кнопок

- `CallbackButton` — кнопка с payload
- `LinkButton` — ссылка
- `ChatButton` — переход в чат
- `MessageButton` — отправка сообщения
- `AttachmentButton` — вложение
- `OpenAppButton` — открытие приложения
- `RequestContact` — запрос контакта
- `RequestGeoLocationButton` — запрос геолокации
