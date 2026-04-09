"""
Эхо-бот — простейший пример бота на maxapi.

Бот отвечает на команду /start приветствием,
а на любое текстовое сообщение — его же текстом.

Демонстрирует:
- Создание Bot и Dispatcher
- Обработку /start через CommandStart
- Обработку BotStarted (кнопка «Начать»)
- Эхо текстовых сообщений с фильтром F.message.body.text
- SenderAction.TYPING_ON — индикатор «печатает...»
- Запуск через dp.start_polling(bot)

Аналог Telegram: python-telegram-bot EchoBot example.

Запуск:
    MAX_BOT_TOKEN=your_token python 01_echo_bot.py
"""

import asyncio
import logging

from dotenv import load_dotenv
from maxapi import Bot, Dispatcher, F
from maxapi.enums.sender_action import SenderAction
from maxapi.filters.command import CommandStart
from maxapi.types.updates.bot_started import BotStarted
from maxapi.types.updates.message_created import MessageCreated

load_dotenv()
logging.basicConfig(level=logging.INFO)

# Токен читается автоматически из переменной окружения MAX_BOT_TOKEN
bot = Bot()
dp = Dispatcher()


@dp.bot_started()
async def on_bot_started(event: BotStarted) -> None:
    """Пользователь нажал кнопку «Начать» в диалоге с ботом."""
    await bot.send_message(
        user_id=event.user.user_id,
        text="Привет! Я эхо-бот. Напиши мне что-нибудь, и я повторю.",
    )


@dp.message_created(CommandStart())
async def on_start(event: MessageCreated) -> None:
    """Обработка команды /start."""
    await event.message.answer(
        "Привет! Я эхо-бот. Отправь мне любое сообщение."
    )


@dp.message_created(F.message.body.text)
async def on_text(event: MessageCreated) -> None:
    """Эхо — повторяем текст пользователя.

    Перед ответом показываем индикатор «печатает...», чтобы бот
    выглядел живым даже при мгновенном ответе.
    """
    chat_id = event.message.recipient.chat_id

    # Показываем индикатор набора текста
    if chat_id is not None:
        await bot.send_action(
            chat_id=chat_id,
            action=SenderAction.TYPING_ON,
        )

    # Защита от None: body и text уже проверены фильтром F.message.body.text,
    # но явная проверка делает намерение очевидным
    text = event.message.body.text if event.message.body else None
    if not text:
        return

    await event.message.answer(text)


async def main() -> None:
    """Точка входа — запускаем long-polling."""
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
