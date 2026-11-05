"""
Бот-модератор комментариев к постам канала.

Демонстрирует:
- @dp.comment_created — реакцию на новый комментарий
- @dp.comment_edited — повторную проверку изменённого комментария
- @dp.comment_removed — журнал удалённых комментариев
- event.message.delete() / event.message.reply() — шорткаты
  комментария без ручной передачи message_id поста
- MagicFilter по тексту комментария

События приходят, только если бот — администратор канала с правом
read_all_messages («Читать все сообщения»).

Аналог Telegram: модерация обсуждений через linked discussion group,
но в MAX комментарии — отдельные события, а не сообщения группы.

Запуск:
    MAX_BOT_TOKEN=your_token python 16_comment_moderation_bot.py
"""

import asyncio
import contextlib
import logging
import re

# Опционально: загрузка .env, если установлен python-dotenv
with contextlib.suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv()
from maxapi import Bot, Dispatcher, F
from maxapi.types.updates.comment_created import CommentCreated
from maxapi.types.updates.comment_edited import CommentEdited
from maxapi.types.updates.comment_removed import CommentRemoved

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot()
dp = Dispatcher()

LINK_RE = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)
STOP_WORDS = {"спам", "казино"}


def _violation(text: str | None) -> str | None:
    """Вернуть причину нарушения или None, если текст допустим."""
    if not text:
        return None
    if LINK_RE.search(text):
        return "ссылки в комментариях запрещены"
    lowered = text.lower()
    if any(word in lowered for word in STOP_WORDS):
        return "стоп-слово"
    return None


async def _moderate(event: CommentCreated | CommentEdited) -> None:
    """Удалить комментарий с нарушением и записать причину в лог."""
    reason = _violation(event.message.body.text)
    if reason is None:
        return

    await event.message.delete()
    logger.info(
        "Удалён комментарий %s к посту %s в канале %s: %s",
        event.message.body.mid,
        event.message.post_message_id,
        event.message.recipient.chat_id,
        reason,
    )


@dp.comment_created(F.message.body.text.lower() == "!правила")
async def on_rules(event: CommentCreated) -> None:
    """Ответить на комментарий с запросом правил."""
    await event.message.reply("Без ссылок и рекламы, пожалуйста.")


@dp.comment_created()
async def on_comment_created(event: CommentCreated) -> None:
    """Проверить новый комментарий."""
    await _moderate(event)


@dp.comment_edited()
async def on_comment_edited(event: CommentEdited) -> None:
    """Проверить комментарий после редактирования."""
    await _moderate(event)


@dp.comment_removed()
async def on_comment_removed(event: CommentRemoved) -> None:
    """Залогировать удаление комментария."""
    logger.info(
        "Комментарий %s к посту %s удалён пользователем %s",
        event.message_id,
        event.post_id,
        event.user_id,
    )


async def main() -> None:
    """Точка входа."""
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
