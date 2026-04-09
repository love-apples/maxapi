"""
Webhook-бот с FastAPI — пример интеграции в продакшн-сервер.

Демонстрирует:
- FastAPIMaxWebhook для приёма обновлений через HTTP POST
- Lifespan FastAPI для инициализации диспетчера при старте
- Подписку на webhook при запуске через bot.subscribe_webhook()
- Кастомный GET-маршрут /healthz рядом с webhook-ом
- Проверку секрета (X-Max-Bot-Api-Secret) для безопасности
- Запуск через webhook.run() (uvicorn внутри)

Требования:
    pip install maxapi[fastapi] uvicorn

Переменные окружения:
    MAX_BOT_TOKEN    — токен бота (обязательно)
    WEBHOOK_URL      — публичный URL вебхука (например https://example.com/webhook)
    WEBHOOK_SECRET   — секрет для заголовка X-Max-Bot-Api-Secret (опционально)
    WEBHOOK_HOST     — хост сервера (по умолчанию 0.0.0.0)
    WEBHOOK_PORT     — порт сервера (по умолчанию 8080)
    WEBHOOK_PATH     — путь маршрута (по умолчанию /webhook)

Аналог Telegram: set_webhook, WebhookInfo / aiogram webhook

Запуск:
    MAX_BOT_TOKEN=tok WEBHOOK_URL=https://example.com/webhook \
    python 09_webhook_bot.py
"""

import asyncio
import logging
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from maxapi import Bot, Dispatcher, F
from maxapi.enums.sender_action import SenderAction
from maxapi.enums.update import UpdateType
from maxapi.filters.command import Command, CommandStart
from maxapi.types.updates.bot_started import BotStarted
from maxapi.types.updates.message_callback import MessageCallback
from maxapi.types.updates.message_created import MessageCreated
from maxapi.webhook.fastapi import FastAPIMaxWebhook

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("webhook_bot")

# ---------------------------------------------------------------------------
# Конфигурация из окружения
# ---------------------------------------------------------------------------
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "https://example.com/webhook")
WEBHOOK_SECRET: str | None = os.getenv("WEBHOOK_SECRET") or None
WEBHOOK_HOST: str = os.getenv(
    "WEBHOOK_HOST", "0.0.0.0"
)  # В production используйте 127.0.0.1 за reverse proxy
WEBHOOK_PORT: int = int(os.getenv("WEBHOOK_PORT", "8080"))
WEBHOOK_PATH: str = os.getenv("WEBHOOK_PATH", "/webhook")

bot = Bot()
dp = Dispatcher()

# ---------------------------------------------------------------------------
# Хендлеры
# ---------------------------------------------------------------------------


@dp.on_started()
async def on_dp_started() -> None:
    """Вызывается один раз при старте диспетчера.

    Регистрируем webhook в MAX-платформе, чтобы она слала обновления
    на наш URL.
    """
    log.info("Диспетчер запущен, подписываемся на webhook: %s", WEBHOOK_URL)
    try:
        await bot.subscribe_webhook(
            url=WEBHOOK_URL,
            update_types=[
                UpdateType.MESSAGE_CREATED,
                UpdateType.MESSAGE_CALLBACK,
                UpdateType.BOT_STARTED,
            ],
            secret=WEBHOOK_SECRET,
        )
        log.info("Подписка на webhook зарегистрирована успешно.")
    except Exception as exc:
        log.error("Не удалось зарегистрировать webhook: %s", exc)


@dp.bot_started()
async def on_bot_started(event: BotStarted) -> None:
    """Приветствие при нажатии кнопки «Начать»."""
    await bot.send_message(
        user_id=event.user.user_id,
        text=(
            "Привет! Я работаю через webhook. Напиши /start или задай вопрос."
        ),
    )


@dp.message_created(CommandStart())
async def on_start(event: MessageCreated) -> None:
    """Обработка /start."""
    await event.message.answer(
        "Webhook-бот активен!\n"
        "Попробуй: /ping — проверка связи\n"
        "          /echo <текст> — эхо"
    )


@dp.message_created(Command("ping"))
async def on_ping(event: MessageCreated) -> None:
    """Проверка связи."""
    chat_id = event.message.recipient.chat_id
    if chat_id:
        await bot.send_action(chat_id=chat_id, action=SenderAction.TYPING_ON)
    await event.message.answer("pong!")


@dp.message_created(Command("echo"))
async def on_echo(event: MessageCreated) -> None:
    """Эхо переданного текста."""
    text = event.message.body.text if event.message.body else ""
    # Убираем "/echo " в начале
    payload = text[5:].strip() if len(text) > 5 else ""
    if not payload:
        await event.message.answer("Использование: /echo <текст>")
        return

    chat_id = event.message.recipient.chat_id
    if chat_id:
        await bot.send_action(chat_id=chat_id, action=SenderAction.TYPING_ON)

    await event.message.answer(payload)


@dp.message_created(F.message.body.text)
async def on_text(event: MessageCreated) -> None:
    """Ответ на произвольный текст."""
    await event.message.answer("Получил твоё сообщение через webhook!")


@dp.message_callback()
async def on_callback(event: MessageCallback) -> None:
    """Обработка inline-кнопок."""
    # Подтверждаем получение callback (убираем «часики» на кнопке)
    await event.answer(notification="Получено!")


# ---------------------------------------------------------------------------
# Сборка FastAPI-приложения с кастомным маршрутом
# ---------------------------------------------------------------------------


def build_app():
    """Создать FastAPI-приложение с webhook и дополнительными маршрутами."""
    webhook = FastAPIMaxWebhook(dp=dp, bot=bot, secret=WEBHOOK_SECRET)

    # Lifespan инициализирует диспетчер (вызовет on_dp_started)
    app = FastAPI(
        title="MaxAPI Webhook Bot",
        lifespan=webhook.lifespan,
    )

    # Регистрируем маршрут webhook
    webhook.setup(app, path=WEBHOOK_PATH)

    # Кастомный маршрут: health check для балансировщика нагрузки
    @app.get("/healthz")
    async def healthz() -> JSONResponse:
        """Проверка работоспособности сервера."""
        return JSONResponse({"status": "ok", "webhook_path": WEBHOOK_PATH})

    # Кастомный маршрут: информация о боте
    @app.get("/bot-info")
    async def bot_info() -> JSONResponse:
        """Вернуть базовую информацию о боте."""
        try:
            me = await bot.get_me()
            return JSONResponse(
                {
                    "username": me.username,
                    "user_id": me.user_id,
                    "first_name": me.first_name,
                }
            )
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    return app


async def main() -> None:
    """Точка входа: запуск через uvicorn."""
    app = build_app()
    config = uvicorn.Config(
        app=app,
        host=WEBHOOK_HOST,
        port=WEBHOOK_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    log.info(
        "Запуск webhook-сервера на %s:%d%s",
        WEBHOOK_HOST,
        WEBHOOK_PORT,
        WEBHOOK_PATH,
    )
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
