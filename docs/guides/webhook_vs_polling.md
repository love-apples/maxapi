# Webhook vs Polling

## Polling

```python
async def main():
    await dp.start_polling(bot, skip_updates=False)
```

**Параметры:**

- `bot` — экземпляр бота
- `skip_updates` — пропускать старые события (по умолчанию `False`)

**Плюсы:**

- Простая настройка
- Не требует публичного URL
- Подходит для разработки

**Минусы:**

- Постоянное подключение к API

## Webhook

```python
async def main():
    await dp.handle_webhook(bot, host='localhost', port=8080)
```

**Параметры:**

- `bot` — экземпляр бота
- `host` — хост сервера (по умолчанию `'localhost'`)
- `port` — порт сервера (по умолчанию `8080`)
- `**kwargs` — дополнительные параметры для `init_serve`

**Плюсы:**

- Эффективнее для больших нагрузок
- События приходят мгновенно
- Меньше нагрузка на API

**Минусы:**

- Требует публичный URL
- Нужна настройка сервера
- Требует `maxapi[webhook]`


!!! warning "Важно"
    Если у бота есть подписки на Webhook, `start_polling` предупредит об этом в логах. 
    Удалите подписки через `await bot.delete_webhook()`.

