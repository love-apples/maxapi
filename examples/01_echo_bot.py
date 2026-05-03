"""
Эхо-бот — простейший пример бота на maxapi.

Бот отвечает на команду /start приветствием,
а на любое текстовое сообщение — его же текстом.

Демонстрирует:
- Создание Bot
- Отправку сообщений через bot.send_message()
- Индикатор «печатает...» через SenderAction.TYPING_ON
- Получение информации о боте через bot.get_my_info()

Аналог Telegram: python-telegram-bot EchoBot example.

Запуск:
    MAX_BOT_TOKEN=your_token python 01_echo_bot.py
"""

import contextlib
import os

# Опционально: загрузка .env, если установлен python-dotenv
with contextlib.suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv()
from maxapi import Bot
from maxapi.enums.sender_action import SenderAction

# Токен читается автоматически из переменной окружения MAX_BOT_TOKEN
bot = Bot()


def main() -> None:
    """Демонстрация прямого использования Bot API."""
    # Получаем информацию о боте
    info = bot.get_my_info()
    print(f"Бот: {info.name} (ID: {info.user_id})")

    # Пример отправки сообщения пользователю по ID.
    # В реальном боте user_id берётся из входящего обновления (update),
    # здесь для демонстрации читаем из переменной окружения.
    user_id = os.environ.get("MAX_USER_ID")
    if user_id is None:
        print(
            "Установите MAX_USER_ID для демонстрации отправки.\n"
            "Пример: MAX_USER_ID=12345 MAX_BOT_TOKEN=your_token python 01_echo_bot.py"
        )
        return

    # Отправляем приветствие
    bot.send_message(
        user_id=int(user_id),
        text="Привет! Я эхо-бот. Напиши мне что-нибудь, и я повторю.",
    )

    # Показываем индикатор набора текста
    bot.send_action(
        chat_id=int(user_id),
        action=SenderAction.TYPING_ON,
    )

    # «Эхо» — отправляем текст обратно
    echo_text = "Привет от эхо-бота!"
    bot.send_message(
        user_id=int(user_id),
        text=echo_text,
    )
    print(f"Отправлено эхо: {echo_text}")


if __name__ == "__main__":
    main()
