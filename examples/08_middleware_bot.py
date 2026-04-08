"""
Middleware паттерны — пример расширенной обработки событий.

Демонстрирует:
- LoggingMiddleware   — логирует все входящие события с типом и chat_id
- ThrottleMiddleware  — простой rate limiter (не чаще 1 сообщения/сек на user)
- AuthMiddleware      — проверяет user_id против whitelist; блокирует чужих
- ErrorHandlingMiddleware — перехватывает исключения из хендлеров
- Глобальное подключение через dp.middleware()
- Передача произвольных данных из middleware в хендлер через data dict

Аналог Telegram: aiogram Middleware / BaseMiddleware

Запуск:
    MAX_BOT_TOKEN=your_token python 08_middleware_bot.py

Переменные окружения (опционально):
    ALLOWED_USERS — запятая-разделённый список user_id (если пусто — всем)
"""

import asyncio
import logging
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

from maxapi import Bot, Dispatcher, F
from maxapi.filters.command import Command, CommandStart
from maxapi.filters.middleware import BaseMiddleware
from maxapi.types.updates.bot_started import BotStarted
from maxapi.types.updates.message_callback import MessageCallback
from maxapi.types.updates.message_created import MessageCreated

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("mw_bot")

bot = Bot()
dp = Dispatcher()

# Читаем whitelist из окружения; пустой список = нет ограничений
_raw = os.getenv("ALLOWED_USERS", "")
WHITELIST: set[int] = {
    int(x.strip()) for x in _raw.split(",") if x.strip().isdigit()
}


# ---------------------------------------------------------------------------
# 1. LoggingMiddleware — логирует каждое событие
# ---------------------------------------------------------------------------


class LoggingMiddleware(BaseMiddleware):
    """Логирует тип события, chat_id и user_id перед вызовом хендлера."""

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event_object: Any,
        data: dict[str, Any],
    ) -> Any:
        event_type = type(event_object).__name__

        # Пытаемся извлечь chat_id и user_id для лога
        chat_id, user_id = None, None
        if hasattr(event_object, "get_ids"):
            try:
                chat_id, user_id = event_object.get_ids()
            except Exception:
                pass

        log.info("[LOG] %s | chat=%s user=%s", event_type, chat_id, user_id)

        # Передаём метаданные в хендлер через data
        data["event_type"] = event_type
        data["logged_chat_id"] = chat_id

        return await handler(event_object, data)


# ---------------------------------------------------------------------------
# 2. ThrottleMiddleware — не чаще 1 сообщения в секунду на пользователя
# ---------------------------------------------------------------------------


class ThrottleMiddleware(BaseMiddleware):
    """Rate limiter: не более одного события в секунду на user_id."""

    def __init__(self, rate: float = 1.0) -> None:
        # Словарь {user_id: timestamp последнего разрешённого события}
        self._last_call: dict[int, float] = {}
        self._rate = rate  # минимальный интервал в секундах

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event_object: Any,
        data: dict[str, Any],
    ) -> Any:
        user_id: int | None = None

        # Извлекаем user_id из события
        msg = getattr(event_object, "message", None)
        if msg is not None:
            sender = getattr(msg, "sender", None)
            if sender is not None:
                user_id = sender.user_id
        callback = getattr(event_object, "callback", None)
        if callback is not None:
            user_id = callback.user.user_id

        if user_id is not None:
            now = time.monotonic()
            last = self._last_call.get(user_id, 0.0)
            if now - last < self._rate:
                # Слишком частые запросы — молча игнорируем
                log.debug("[THROTTLE] Пропущено событие для user=%s", user_id)
                return None
            self._last_call[user_id] = now

        return await handler(event_object, data)


# ---------------------------------------------------------------------------
# 3. AuthMiddleware — проверяет user_id против whitelist
# ---------------------------------------------------------------------------


class AuthMiddleware(BaseMiddleware):
    """Блокирует обработку событий от пользователей не из whitelist.

    Если WHITELIST пуст — пропускает всех.
    """

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event_object: Any,
        data: dict[str, Any],
    ) -> Any:
        if not WHITELIST:
            # Whitelist не задан — разрешаем всем
            return await handler(event_object, data)

        user_id: int | None = None
        msg = getattr(event_object, "message", None)
        if msg is not None:
            sender = getattr(msg, "sender", None)
            if sender is not None:
                user_id = sender.user_id

        if user_id is None or user_id not in WHITELIST:
            log.warning("[AUTH] Доступ запрещён для user=%s", user_id)
            # Пытаемся ответить «Нет доступа»
            if isinstance(event_object, MessageCreated):
                await event_object.message.answer(
                    "У вас нет доступа к этому боту."
                )
            return None

        data["is_authorized"] = True
        return await handler(event_object, data)


# ---------------------------------------------------------------------------
# 4. ErrorHandlingMiddleware — перехватывает исключения хендлеров
# ---------------------------------------------------------------------------


class ErrorHandlingMiddleware(BaseMiddleware):
    """Перехватывает необработанные исключения из хендлеров."""

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event_object: Any,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event_object, data)
        except Exception as exc:
            log.exception(
                "[ERROR] Необработанное исключение в хендлере: %s", exc
            )
            # Сообщаем пользователю об ошибке
            if isinstance(event_object, MessageCreated):
                await event_object.message.answer(
                    "Произошла внутренняя ошибка. Попробуйте позже."
                )
            elif isinstance(event_object, MessageCallback):
                await event_object.answer(
                    notification="Ошибка обработки запроса."
                )
            return None


# ---------------------------------------------------------------------------
# Глобальная регистрация middleware (порядок важен: outer → inner)
# ---------------------------------------------------------------------------

# ErrorHandling — самый внешний, ловит ошибки из всей цепочки ниже
dp.outer_middleware(ErrorHandlingMiddleware())
# Logging — следующий
dp.middleware(LoggingMiddleware())
# Auth — проверяет права
dp.middleware(AuthMiddleware())
# Throttle — последний перед хендлером
dp.middleware(ThrottleMiddleware(rate=1.0))


# ---------------------------------------------------------------------------
# Хендлеры
# ---------------------------------------------------------------------------


@dp.bot_started()
async def on_start(event: BotStarted) -> None:
    """Приветствие."""
    await bot.send_message(
        user_id=event.user.user_id,
        text="Бот с middleware запущен. Попробуй отправить любое сообщение.",
    )


@dp.message_created(CommandStart())
async def on_cmd_start(event: MessageCreated) -> None:
    """Обработка /start."""
    await event.message.answer("Привет! Все middleware активны.")


@dp.message_created(Command("crash"))
async def on_crash(event: MessageCreated) -> None:
    """Бросаем исключение для демонстрации ErrorHandlingMiddleware."""
    msg = "Тестовое исключение для демонстрации ErrorHandlingMiddleware"
    raise RuntimeError(msg)


@dp.message_created(F.message.body.text)
async def on_text(
    event: MessageCreated,
    event_type: str = "unknown",
    logged_chat_id: int | None = None,
    is_authorized: bool = False,
) -> None:
    """Эхо с данными из middleware.

    Параметры event_type, logged_chat_id, is_authorized инжектируются из data.
    """
    text = event.message.body.text if event.message.body else ""
    await event.message.answer(
        f"Получено: «{text}»\n"
        f"Тип: {event_type}\n"
        f"Chat: {logged_chat_id}\n"
        f"Авторизован: {is_authorized}"
    )


async def main() -> None:
    """Точка входа."""
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
