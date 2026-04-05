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
    webhook_url = 'https://ваш-домен.рф/webhook'  # <-- укажите свой
    await bot.subscribe_webhook(url=webhook_url)
    await dp.handle_webhook(bot, host='0.0.0.0', port=8080)
```

**Параметры:**

- `bot` — экземпляр бота
- `host` — хост сервера (по умолчанию `'0.0.0.0'`)
- `port` — порт сервера (по умолчанию `8080`)
- `path` — URL-путь для маршрута вебхука (по умолчанию `'/'`)
- `secret` — секрет для проверки заголовка `X-Max-Bot-Api-Secret`
- `**kwargs` — дополнительные параметры для запуска веб-сервера

**Плюсы:**

- Эффективнее для больших нагрузок
- События приходят мгновенно
- Меньше нагрузка на API

**Минусы:**

- Требует публичный URL
- Нужна настройка сервера


!!! warning "Важно"
    Если у бота есть подписки на Webhook, `start_polling` предупредит об этом в логах. 
    Удалите подписки через `await bot.delete_webhook()`.
