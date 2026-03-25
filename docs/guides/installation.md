# Установка

## Через pip

```bash
pip install maxapi
```

## Webhook

Webhook-сервер на `aiohttp` уже входит в базовый пакет — дополнительных зависимостей не требуется.

## Опциональные зависимости для ASGI-фреймворков

Если вы хотите использовать **FastAPI** или **Litestar** вместо встроенного aiohttp-сервера:

```bash
pip install maxapi[fastapi]   # FastAPI + uvicorn
pip install maxapi[litestar]  # Litestar + uvicorn
```

## Из GitHub

```bash
pip install git+https://github.com/love-apples/maxapi.git
```

## Требования

- Python 3.10+
- Токен бота MAX
