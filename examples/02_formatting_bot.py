"""
Бот форматирования — демонстрация разметки текста в maxapi.

Демонстрирует:
- Bold, Italic, Underline, Strikethrough, Code (инлайн и блок)
- Heading — заголовок
- Link — гиперссылка
- UserMention — упоминание пользователя
- Text-контейнер для комбинирования элементов
- Методы as_html() и as_markdown() для получения строки
- TextFormat enum для выбора режима отображения

Команды:
    /html      — пример с HTML-разметкой
    /markdown  — пример с Markdown-разметкой
    /mention   — упоминание отправителя
    /all       — все виды форматирования сразу

Аналог Telegram: parse_mode=HTML / aiogram formatting helpers

Запуск:
    MAX_BOT_TOKEN=your_token python 02_formatting_bot.py
"""

import asyncio
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from maxapi import Bot, Dispatcher
from maxapi.enums.parse_mode import TextFormat
from maxapi.filters.command import Command, CommandStart
from maxapi.types.updates.message_created import MessageCreated

# Импорты билдеров форматирования
from maxapi.utils.formatting import (
    Bold,
    Code,
    Heading,
    Italic,
    Link,
    Strikethrough,
    Text,
    Underline,
    UserMention,
)

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()

# Текст подсказки со списком доступных команд
HELP_TEXT = (
    "Доступные команды:\n"
    "/html      — пример HTML-форматирования\n"
    "/markdown  — пример Markdown-форматирования\n"
    "/mention   — упоминание вас\n"
    "/all       — все элементы сразу"
)


@dp.message_created(CommandStart())
async def on_start(event: MessageCreated) -> None:
    """Приветствие с перечнем команд."""
    await event.message.answer(HELP_TEXT)


@dp.message_created(Command("html"))
async def on_html(event: MessageCreated) -> None:
    """Пример форматирования, выведенный через as_html()."""
    # Собираем составной текст из отдельных элементов
    content = Text(
        Bold("Жирный"),
        " | ",
        Italic("Курсив"),
        " | ",
        Underline("Подчёркнутый"),
        " | ",
        Strikethrough("Зачёркнутый"),
        "\n\n",
        Heading("Это заголовок"),
        "\n",
        Code("print('Hello, Max!')"),
        "\n\n",
        Link("Открыть Max.ru", url="https://max.ru"),
    )

    # Отправляем сообщение в HTML-режиме
    await event.message.answer(
        content.as_html(),
        format=TextFormat.HTML,
    )


@dp.message_created(Command("markdown"))
async def on_markdown(event: MessageCreated) -> None:
    """Пример форматирования, выведенный через as_markdown()."""
    content = Text(
        Bold("Жирный"),
        " | ",
        Italic("Курсив"),
        " | ",
        Strikethrough("Зачёркнутый"),
        "\n\n",
        Code("x = 42  # Markdown инлайн-код"),
        "\n\n",
        Link(
            "Документация maxapi",
            url="https://github.com/max-messenger/maxapi",
        ),
    )

    await event.message.answer(
        content.as_markdown(),
        format=TextFormat.MARKDOWN,
    )


@dp.message_created(Command("mention"))
async def on_mention(event: MessageCreated) -> None:
    """Упоминание отправителя сообщения."""
    sender = event.message.sender
    if sender is None:
        await event.message.answer("Не удалось определить отправителя.")
        return

    content = Text(
        "Привет, ",
        UserMention(
            sender.full_name or "пользователь",
            user_id=sender.user_id,
        ),
        "! Вы упомянуты.",
    )

    await event.message.answer(
        content.as_html(),
        format=TextFormat.HTML,
    )


@dp.message_created(Command("all"))
async def on_all(event: MessageCreated) -> None:
    """Все доступные элементы форматирования в одном сообщении."""
    content = Text(
        Heading("Все виды форматирования"),
        "\n\n",
        Bold("Жирный текст"),
        "\n",
        Italic("Курсивный текст"),
        "\n",
        Underline("Подчёркнутый текст"),
        "\n",
        Strikethrough("Зачёркнутый текст"),
        "\n",
        Code("inline_code()"),
        "\n\n",
        "Блок кода:\n",
        Code("def hello():\n    return 'world'"),
        "\n\n",
        Link("Ссылка на Max", url="https://max.ru"),
    )

    await event.message.answer(
        content.as_html(),
        format=TextFormat.HTML,
    )


async def main() -> None:
    """Точка входа."""
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
