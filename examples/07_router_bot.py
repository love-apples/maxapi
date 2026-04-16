"""
Модульная архитектура с роутерами — пример структурирования бота.

Демонстрирует:
- Создание трёх Router-ов: general_router, admin_router, quiz_router
- Роутер-уровневые фильтры (admin_router принимает только chat-тип CHAT)
- Роутер-уровневые middleware (логирование для admin_router)
- Подключение роутеров через dp.include_routers()
- Изоляцию логики: каждый роутер отвечает за свою предметную область
- Передачу данных через data dict в middleware

Аналог Telegram: aiogram Router / python-telegram-bot ConversationHandler

Запуск:
    MAX_BOT_TOKEN=your_token python 07_router_bot.py
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass
from maxapi import Bot, Dispatcher, F
from maxapi.dispatcher import Router
from maxapi.enums.chat_type import ChatType
from maxapi.enums.sender_action import SenderAction
from maxapi.filters.command import Command, CommandStart
from maxapi.filters.filter import BaseFilter
from maxapi.filters.middleware import BaseMiddleware
from maxapi.types.updates import UpdateUnion
from maxapi.types.updates.bot_started import BotStarted
from maxapi.types.updates.message_created import MessageCreated

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s"
)
log = logging.getLogger("router_bot")

bot = Bot()
dp = Dispatcher()


# ---------------------------------------------------------------------------
# Middleware: логирование входящих событий (только для admin_router)
# ---------------------------------------------------------------------------


class AdminLoggingMiddleware(BaseMiddleware):
    """Логирует все события, проходящие через admin_router."""

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event_object: Any,
        data: dict[str, Any],
    ) -> Any:
        # Добавляем метку в data, чтобы хендлер знал, что прошёл admin-путь
        data["admin_logged"] = True
        log.info("[ADMIN] Событие: %s", type(event_object).__name__)
        return await handler(event_object, data)


# ---------------------------------------------------------------------------
# Фильтр: только групповые чаты (не личные диалоги)
# ---------------------------------------------------------------------------


class ChatOnlyFilter(BaseFilter):
    """Пропускает только события из групповых чатов (chat_type == CHAT)."""

    async def __call__(self, event: UpdateUnion) -> bool:
        msg = getattr(event, "message", None)
        if msg is None:
            return False
        return msg.recipient.chat_type == ChatType.CHAT


# ---------------------------------------------------------------------------
# general_router — общие команды, работают везде
# ---------------------------------------------------------------------------

general_router = Router(router_id="general")


@general_router.bot_started()
async def on_start(event: BotStarted) -> None:
    """Приветствие при старте."""
    await bot.send_message(
        user_id=event.user.user_id,
        text="Привет! Это бот с модульной архитектурой.\n/help — справка",
    )


@general_router.message_created(CommandStart())
async def on_cmd_start(event: MessageCreated) -> None:
    """Обработка /start."""
    await event.message.answer(
        "Привет! Доступные команды:\n"
        "/help — справка\n"
        "/quiz — запустить викторину (в группе)\n"
        "/status — статус администратора (в группе)"
    )


@general_router.message_created(Command("help"))
async def on_help(event: MessageCreated) -> None:
    """Справка по командам."""
    await event.message.answer(
        "Общие команды работают везде.\n"
        "Команды /quiz и /status — только в групповых чатах."
    )


# ---------------------------------------------------------------------------
# admin_router — команды для групповых чатов с логированием
# ---------------------------------------------------------------------------

admin_router = Router(router_id="admin")
# Роутер-уровневый фильтр: только групповые чаты
admin_router.filter(ChatOnlyFilter())
# Роутер-уровневый middleware: логирование
admin_router.middleware(AdminLoggingMiddleware())


@admin_router.message_created(Command("status"))
async def on_status(event: MessageCreated, admin_logged: bool = False) -> None:
    """Показать статус администратора в чате.

    Параметр admin_logged инжектируется из data-словаря middleware.
    """
    chat_id = event.message.recipient.chat_id
    if chat_id is None:
        return

    await bot.send_action(chat_id=chat_id, action=SenderAction.TYPING_ON)

    label = " [залогировано]" if admin_logged else ""
    await event.message.answer(f"Статус: бот активен в этом чате.{label}")


# ---------------------------------------------------------------------------
# quiz_router — простая викторина, только в групповых чатах
# ---------------------------------------------------------------------------

quiz_router = Router(router_id="quiz")
quiz_router.filter(ChatOnlyFilter())

# Вопросы викторины: {вопрос: правильный_ответ}
QUIZ: dict[str, str] = {
    "Сколько планет в Солнечной системе?": "8",
    "Столица Франции?": "paris",
    "Квадратный корень из 144?": "12",
}
# Текущий вопрос по chat_id
active_questions: dict[int, tuple[str, str]] = {}


@quiz_router.message_created(Command("quiz"))
async def on_quiz_start(event: MessageCreated) -> None:
    """Начать новый раунд викторины."""
    chat_id = event.message.recipient.chat_id
    if chat_id is None:
        return

    # Берём первый вопрос из словаря
    question, answer = next(iter(QUIZ.items()))
    active_questions[chat_id] = (question, answer)

    await event.message.answer(f"Викторина! Ответьте на вопрос:\n{question}")


@quiz_router.message_created(F.message.body.text)
async def on_quiz_answer(event: MessageCreated) -> None:
    """Проверить ответ на вопрос викторины."""
    chat_id = event.message.recipient.chat_id
    if chat_id is None or chat_id not in active_questions:
        return

    text = event.message.body.text if event.message.body else None
    if not text:
        return

    _, correct = active_questions[chat_id]
    if text.strip().lower() == correct.lower():
        del active_questions[chat_id]
        await event.message.answer(
            "Правильно! Викторина завершена. /quiz — сыграть ещё."
        )
    else:
        await event.message.answer("Неверно, попробуйте ещё раз.")


# ---------------------------------------------------------------------------
# Подключение роутеров к диспетчеру
# ---------------------------------------------------------------------------

dp.include_routers(general_router, admin_router, quiz_router)


async def main() -> None:
    """Точка входа."""
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
