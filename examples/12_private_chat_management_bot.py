"""
Управление участниками закрытого чата.

Демонстрирует:
- /members — список участников через bot.get_chat_members()
- /add <user_id> [user_id ...] — добавление участников
- /kick <user_id> — удаление участника
- /block <user_id> — удаление и блокировка участника
- /link — ссылка чата, если MAX API возвращает её в Chat.link

Важно: генерация новой пригласительной ссылки и одобрение заявок на
вступление пока не представлены отдельными методами MAX Bot API в SDK.

Запуск:
    MAX_BOT_TOKEN=your_token python 12_private_chat_management_bot.py
"""

import asyncio
import contextlib
import logging

with contextlib.suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv()

from maxapi import Bot, Dispatcher
from maxapi.filters.command import Command, CommandStart
from maxapi.types.updates.bot_started import BotStarted
from maxapi.types.updates.message_created import MessageCreated

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot()
dp = Dispatcher()


def _get_chat_id(event: MessageCreated) -> int | None:
    return event.message.recipient.chat_id


def _parse_user_ids(args: list[str]) -> list[int]:
    try:
        return [int(arg) for arg in args]
    except ValueError as exc:
        msg = "Все user_id должны быть числами."
        raise ValueError(msg) from exc


async def _answer_chat_only(event: MessageCreated) -> int | None:
    chat_id = _get_chat_id(event)
    if chat_id is None:
        await event.message.answer("Команда работает только в чате.")
        return None

    return chat_id


@dp.bot_started()
async def on_start(event: BotStarted) -> None:
    """Отправить подсказку при запуске диалога с ботом."""

    await bot.send_message(
        user_id=event.user.user_id,
        text=(
            "Команды управления закрытым чатом:\n"
            "/members — список участников\n"
            "/add <user_id> [user_id ...] — добавить участников\n"
            "/kick <user_id> — удалить участника\n"
            "/block <user_id> — удалить и заблокировать\n"
            "/link — показать ссылку чата, если она доступна"
        ),
    )


@dp.message_created(CommandStart())
async def on_cmd_start(event: MessageCreated) -> None:
    """Показать список команд."""

    await event.message.answer(
        "Я помогу управлять участниками закрытого чата. "
        "Попробуйте /members, /add, /kick, /block или /link."
    )


@dp.message_created(Command("members"))
async def on_members(event: MessageCreated) -> None:
    """Показать первые 20 участников текущего чата."""

    chat_id = await _answer_chat_only(event)
    if chat_id is None:
        return

    try:
        result = await bot.get_chat_members(chat_id=chat_id, count=20)
        if not result.members:
            await event.message.answer("Список участников пуст.")
            return

        lines = [
            member.full_name or f"id:{member.user_id}"
            for member in result.members
        ]
        await event.message.answer("Участники:\n" + "\n".join(lines))
    except Exception as exc:
        logger.exception(exc)
        await event.message.answer("Не удалось получить участников.")


@dp.message_created(Command("add"))
async def on_add(event: MessageCreated, args: list[str]) -> None:
    """Добавить участников в текущий чат."""

    chat_id = await _answer_chat_only(event)
    if chat_id is None:
        return

    if not args:
        await event.message.answer("Использование: /add <user_id> [...]")
        return

    try:
        user_ids = _parse_user_ids(args)
        result = await bot.add_chat_members(
            chat_id=chat_id,
            user_ids=user_ids,
        )
    except ValueError as exc:
        await event.message.answer(str(exc))
        return
    except Exception as exc:
        logger.exception(exc)
        await event.message.answer("Не удалось добавить участников.")
        return

    if result.success:
        await event.message.answer("Участники добавлены.")
        return

    failed_ids = result.failed_user_ids or []
    details = ", ".join(str(user_id) for user_id in failed_ids) or "нет"
    await event.message.answer(
        f"Не все участники добавлены. Ошибка: {result.message or 'нет'}; "
        f"failed_user_ids: {details}."
    )


@dp.message_created(Command("kick"))
async def on_kick(event: MessageCreated, args: list[str]) -> None:
    """Удалить участника из текущего чата."""

    await _remove_member(event, args=args, block=False)


@dp.message_created(Command("block"))
async def on_block(event: MessageCreated, args: list[str]) -> None:
    """Удалить участника из текущего чата и заблокировать его."""

    await _remove_member(event, args=args, block=True)


async def _remove_member(
    event: MessageCreated,
    *,
    args: list[str],
    block: bool,
) -> None:
    chat_id = await _answer_chat_only(event)
    if chat_id is None:
        return

    if len(args) != 1:
        command = "/block" if block else "/kick"
        await event.message.answer(f"Использование: {command} <user_id>")
        return

    try:
        user_id = _parse_user_ids(args)[0]
        await bot.kick_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            block=block,
        )
    except ValueError as exc:
        await event.message.answer(str(exc))
        return
    except Exception as exc:
        logger.exception(exc)
        await event.message.answer("Не удалось удалить участника.")
        return

    action = "заблокирован" if block else "удалён"
    await event.message.answer(f"Участник {user_id} {action}.")


@dp.message_created(Command("link"))
async def on_link(event: MessageCreated) -> None:
    """Показать ссылку текущего чата, если она есть в Chat.link."""

    chat_id = await _answer_chat_only(event)
    if chat_id is None:
        return

    try:
        chat = await bot.get_chat_by_id(id=chat_id)
    except Exception as exc:
        logger.exception(exc)
        await event.message.answer("Не удалось получить информацию о чате.")
        return

    if chat.link:
        await event.message.answer(f"Ссылка чата: {chat.link}")
        return

    await event.message.answer(
        "MAX API не вернул ссылку для этого чата. "
        "Отдельного метода генерации invite-link в SDK пока нет."
    )


async def main() -> None:
    """Точка входа."""

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
