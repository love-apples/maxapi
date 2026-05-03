"""
Бот-администратор чата — пример управления сообщениями и участниками.

Демонстрирует:
- bot.send_message() — отправка сообщений
- bot.pin_message() — закрепление сообщения
- bot.delete_message() — удаление сообщения
- bot.edit_message() — редактирование сообщения
- bot.get_chat_by_id() — получение информации о чате
- bot.get_chat_members() — список участников чата
- bot.send_action() — индикатор «печатает...»

Аналог Telegram: pin_chat_message, delete_message, edit_message_text

Запуск:
    MAX_BOT_TOKEN=your_token python 06_admin_bot.py
"""

import contextlib
import logging
import os

# Опционально: загрузка .env, если установлен python-dotenv
with contextlib.suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv()
from maxapi import Bot
from maxapi.enums.sender_action import SenderAction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot()


def main() -> None:
    """Демонстрация административных методов Bot API."""
    # В реальном боте chat_id/user_id берётся из входящего обновления (update),
    # здесь для демонстрации читаем из переменных окружения.
    chat_id = os.environ.get("MAX_CHAT_ID")
    user_id = os.environ.get("MAX_USER_ID")

    if chat_id is None and user_id is None:
        print(
            "Установите MAX_CHAT_ID или MAX_USER_ID для демонстрации.\n"
            "Пример:\n"
            "  MAX_CHAT_ID=chat123 MAX_BOT_TOKEN=your_token python 06_admin_bot.py\n"
            "  MAX_USER_ID=12345 MAX_BOT_TOKEN=your_token python 06_admin_bot.py"
        )
        return

    # ── 1. Отправка приветственного сообщения ────────────────────────────
    target_id = int(chat_id) if chat_id else int(user_id)
    print("Отправка приветственного сообщения...")
    sent = bot.send_message(
        chat_id=int(chat_id) if chat_id else None,
        user_id=int(user_id) if user_id else None,
        text=(
            "Привет! Я бот-администратор.\n"
            "Демонстрация административных команд:"
        ),
    )

    if not sent or not sent.message or not sent.message.body:
        print("Не удалось отправить сообщение.")
        return

    mid = sent.message.body.mid
    print(f"Сообщение отправлено, message_id: {mid}")

    # ── 2. Редактирование сообщения ───────────────────────────────────────
    print("Редактирование сообщения...")
    try:
        bot.edit_message(
            message_id=mid,
            text="[Отредактировано] Исходный текст был изменён администратором.",
        )
        print("Сообщение отредактировано.")
    except Exception as exc:
        logger.exception(exc)
        print("Не удалось отредактировать.")

    # ── 3. Закрепление сообщения ──────────────────────────────────────────
    if chat_id:
        print("Закрепление сообщения...")
        try:
            bot.send_action(chat_id=int(chat_id), action=SenderAction.TYPING_ON)
            bot.pin_message(chat_id=int(chat_id), message_id=mid)
            print("Сообщение закреплено.")
        except Exception as exc:
            logger.exception(exc)
            print("Не удалось закрепить.")

        # ── 4. Получение информации о чате ─────────────────────────────────
        print("Получение информации о чате...")
        try:
            chat = bot.get_chat_by_id(id=int(chat_id))
            text = (
                f"Чат: {chat.title or '(без названия)'}\n"
                f"ID: {chat.chat_id}\n"
                f"Тип: {chat.type}\n"
                f"Участников: {chat.participants_count or '-'}"
            )
            print(text)
        except Exception as exc:
            logger.exception(exc)
            print("Ошибка получения информации.")

        # ── 5. Получение списка участников ─────────────────────────────────
        print("Получение списка участников...")
        try:
            result = bot.get_chat_members(chat_id=int(chat_id), count=10)
            members = result.members or []
            if members:
                for m in members:
                    name = m.full_name or f"id:{m.user_id}"
                    print(f"  - {name}")
            else:
                print("Список участников пуст.")
        except Exception as exc:
            logger.exception(exc)
            print("Ошибка получения участников.")

    # ── 6. Удаление сообщения ─────────────────────────────────────────────
    print("Удаление сообщения...")
    try:
        bot.delete_message(message_id=mid)
        print("Сообщение удалено.")
    except Exception as exc:
        logger.exception(exc)
        print("Не удалось удалить.")

    print("Готово!")


if __name__ == "__main__":
    main()
