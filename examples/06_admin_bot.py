"""
Бот-администратор чата — пример управления сообщениями и участниками.

Демонстрирует:
- /pin   — закрепление сообщения (reply) через bot.pin_message()
- /delete — удаление сообщения (reply) через message.delete()
- /edit   — редактирование последнего сообщения бота через bot.edit_message()
- /info   — получение информации о чате через bot.get_chat_by_id()
- /members — список участников через bot.get_chat_members()
- Обработку chat_title_changed (смена названия чата)
- Обработку user_added / user_removed (приветствие / прощание)

Аналог Telegram: pin_chat_message, delete_message, edit_message_text

Запуск:
    MAX_BOT_TOKEN=your_token python 06_admin_bot.py
"""

import asyncio
import logging

from maxapi import Bot, Dispatcher
from maxapi.enums.sender_action import SenderAction
from maxapi.filters.command import Command, CommandStart
from maxapi.types.updates.bot_started import BotStarted
from maxapi.types.updates.chat_title_changed import ChatTitleChanged
from maxapi.types.updates.message_created import MessageCreated
from maxapi.types.updates.user_added import UserAdded
from maxapi.types.updates.user_removed import UserRemoved

logger = logging.getLogger(__name__)

bot = Bot()
dp = Dispatcher()

# Хранилище последнего message_id бота по chat_id (для /edit)
last_bot_message: dict[int, str] = {}


@dp.bot_started()
async def on_start(event: BotStarted) -> None:
    """Приветствие при старте в личном диалоге."""
    await bot.send_message(
        user_id=event.user.user_id,
        text=(
            "Привет! Я бот-администратор.\n"
            "Команды:\n"
            "/pin — закрепить (reply)\n"
            "/delete — удалить (reply)\n"
            "/edit — редактировать моё последнее сообщение\n"
            "/info — информация о чате\n"
            "/members — список участников"
        ),
    )


@dp.message_created(CommandStart())
async def on_cmd_start(event: MessageCreated) -> None:
    """Обработка команды /start."""
    await event.message.answer(
        "Готов к работе! Используй команды для управления чатом."
    )


@dp.message_created(Command("pin"))
async def on_pin(event: MessageCreated) -> None:
    """Закрепить сообщение, на которое ответили командой /pin."""
    linked = event.message.link
    if linked is None:
        await event.message.answer(
            "Ответьте командой /pin на то сообщение, которое нужно закрепить."
        )
        return

    chat_id = event.message.recipient.chat_id
    if chat_id is None:
        return

    await bot.send_action(chat_id=chat_id, action=SenderAction.TYPING_ON)

    try:
        await bot.pin_message(chat_id=chat_id, message_id=linked.message.mid)
        await event.message.answer("Сообщение закреплено.")
    except Exception as exc:
        logger.exception(exc)
        await event.message.answer("Не удалось закрепить.")


@dp.message_created(Command("delete"))
async def on_delete(event: MessageCreated) -> None:
    """Удалить сообщение, на которое ответили командой /delete."""
    linked = event.message.link
    if linked is None:
        await event.message.answer(
            "Ответьте командой /delete на сообщение, которое нужно удалить."
        )
        return

    try:
        await bot.delete_message(message_id=linked.message.mid)
        await event.message.answer("Сообщение удалено.")
    except Exception as exc:
        logger.exception(exc)
        await event.message.answer("Не удалось удалить.")


@dp.message_created(Command("edit"))
async def on_edit(event: MessageCreated) -> None:
    """Редактировать последнее сообщение бота в этом чате."""
    chat_id = event.message.recipient.chat_id
    if chat_id is None:
        return

    mid = last_bot_message.get(chat_id)
    if mid is None:
        sent = await event.message.answer(
            "Это сообщение будет отредактировано командой /edit."
        )
        if sent and sent.message and sent.message.body:
            last_bot_message[chat_id] = sent.message.body.mid
        return

    try:
        await bot.edit_message(
            message_id=mid,
            text=(
                "[Отредактировано] Исходный текст был изменён администратором."
            ),
        )
        await event.message.answer("Сообщение отредактировано.")
    except Exception as exc:
        logger.exception(exc)
        await event.message.answer("Не удалось отредактировать.")


@dp.message_created(Command("info"))
async def on_info(event: MessageCreated) -> None:
    """Получить информацию о текущем чате."""
    chat_id = event.message.recipient.chat_id
    if chat_id is None:
        await event.message.answer("Эта команда работает только в чатах.")
        return

    await bot.send_action(chat_id=chat_id, action=SenderAction.TYPING_ON)

    try:
        chat = await bot.get_chat_by_id(id=chat_id)
        text = (
            f"Чат: {chat.title or '(без названия)'}\n"
            f"ID: {chat.chat_id}\n"
            f"Тип: {chat.type}\n"
            f"Участников: {chat.participants_count or '—'}"
        )
        await event.message.answer(text)
    except Exception as exc:
        logger.exception(exc)
        await event.message.answer("Ошибка получения информации.")


@dp.message_created(Command("members"))
async def on_members(event: MessageCreated) -> None:
    """Показать список участников чата (первые 10)."""
    chat_id = event.message.recipient.chat_id
    if chat_id is None:
        await event.message.answer("Команда работает только в чатах.")
        return

    await bot.send_action(chat_id=chat_id, action=SenderAction.TYPING_ON)

    try:
        result = await bot.get_chat_members(chat_id=chat_id, count=10)
        members = result.members or []
        if not members:
            await event.message.answer("Список участников пуст.")
            return

        lines = []
        for m in members:
            name = m.full_name or f"id:{m.user_id}"
            lines.append(f"• {name}")

        await event.message.answer("Участники чата:\n" + "\n".join(lines))
    except Exception as exc:
        logger.exception(exc)
        await event.message.answer("Ошибка получения участников.")


@dp.chat_title_changed()
async def on_title_changed(event: ChatTitleChanged) -> None:
    """Уведомление при изменении названия чата."""
    changer = event.user.full_name or f"id:{event.user.user_id}"
    await bot.send_message(
        chat_id=event.chat_id,
        text=(
            f"Название чата изменено на «{event.title}» "
            f"пользователем {changer}."
        ),
    )


@dp.user_added()
async def on_user_added(event: UserAdded) -> None:
    """Приветствие нового участника чата."""
    name = event.user.full_name or f"id:{event.user.user_id}"
    await bot.send_message(
        chat_id=event.chat_id,
        text=f"Добро пожаловать в чат, {name}!",
    )


@dp.user_removed()
async def on_user_removed(event: UserRemoved) -> None:
    """Прощание при выходе участника из чата."""
    name = event.user.full_name or f"id:{event.user.user_id}"
    await bot.send_message(
        chat_id=event.chat_id,
        text=f"{name} покинул чат. До свидания!",
    )


async def main() -> None:
    """Точка входа."""
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
