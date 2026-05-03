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

Аналог Telegram: parse_mode=HTML / aiogram formatting helpers

Запуск:
    MAX_BOT_TOKEN=your_token python 02_formatting_bot.py
"""

import contextlib
import os

# Опционально: загрузка .env, если установлен python-dotenv
with contextlib.suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv()
from maxapi import Bot
from maxapi.enums.parse_mode import TextFormat

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

bot = Bot()


def demo_html(user_id: int) -> None:
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
    bot.send_message(
        user_id=user_id,
        text=content.as_html(),
        format=TextFormat.HTML,
    )


def demo_markdown(user_id: int) -> None:
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

    bot.send_message(
        user_id=user_id,
        text=content.as_markdown(),
        format=TextFormat.MARKDOWN,
    )


def demo_mention(user_id: int) -> None:
    """Упоминание пользователя."""
    content = Text(
        "Привет, ",
        UserMention(
            "пользователь",
            user_id=user_id,
        ),
        "! Вы упомянуты.",
    )

    bot.send_message(
        user_id=user_id,
        text=content.as_html(),
        format=TextFormat.HTML,
    )


def demo_all(user_id: int) -> None:
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

    bot.send_message(
        user_id=user_id,
        text=content.as_html(),
        format=TextFormat.HTML,
    )


def main() -> None:
    """Демонстрация форматирования текста через Bot API."""
    # Пример отправки форматированного сообщения пользователю.
    # В реальном боте user_id берётся из входящего обновления (update),
    # здесь для демонстрации читаем из переменной окружения.
    user_id = os.environ.get("MAX_USER_ID")
    if user_id is None:
        print(
            "Установите MAX_USER_ID для демонстрации отправки.\n"
            "Пример: MAX_USER_ID=12345 MAX_BOT_TOKEN=your_token python 02_formatting_bot.py"
        )
        return

    uid = int(user_id)

    print("Отправка HTML-форматирования...")
    demo_html(uid)

    print("Отправка Markdown-форматирования...")
    demo_markdown(uid)

    print("Отправка упоминания пользователя...")
    demo_mention(uid)

    print("Отправка всех видов форматирования...")
    demo_all(uid)

    print("Готово!")


if __name__ == "__main__":
    main()
