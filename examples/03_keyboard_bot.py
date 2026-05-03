"""
Бот с клавиатурами — полный пример работы с inline-кнопками в maxapi.

Демонстрирует:
- InlineKeyboardBuilder — построитель inline-клавиатуры
- CallbackButton с payload-строкой
- LinkButton — кнопка-ссылка
- RequestContactButton — запрос контакта пользователя
- RequestGeoLocationButton — запрос геолокации
- Отправку клавиатуры через bot.send_message()
- Редактирование сообщения через bot.edit_message()
- Удаление клавиатуры через пустой список attachments

Аналог Telegram: InlineKeyboardMarkup, aiogram InlineKeyboardBuilder

Запуск:
    MAX_BOT_TOKEN=your_token python 03_keyboard_bot.py
"""

import contextlib
import os

# Опционально: загрузка .env, если установлен python-dotenv
with contextlib.suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv()
from maxapi import Bot
from maxapi.types.attachments.buttons.callback_button import CallbackButton
from maxapi.types.attachments.buttons.link_button import LinkButton
from maxapi.types.attachments.buttons.request_contact import (
    RequestContactButton,
)
from maxapi.types.attachments.buttons.request_geo_location_button import (
    RequestGeoLocationButton,
)
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

bot = Bot()

# ── Константы payload для callback-кнопок ──────────────────────────────────
CB_MENU = "menu"
CB_INFO = "info"
CB_CONTACT = "contact"
CB_GEO = "geo"
CB_BACK = "back"
CB_CLOSE = "close"


def build_main_keyboard() -> InlineKeyboardBuilder:
    """Главное меню с четырьмя кнопками."""
    kb = InlineKeyboardBuilder()
    kb.row(
        CallbackButton(text="Информация", payload=CB_INFO),
        CallbackButton(text="Запросить контакт", payload=CB_CONTACT),
    )
    kb.row(
        CallbackButton(text="Запросить геолокацию", payload=CB_GEO),
        LinkButton(text="Открыть Max", url="https://max.ru"),
    )
    return kb


def build_info_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура с кнопкой «Назад» для экрана информации."""
    kb = InlineKeyboardBuilder()
    kb.row(CallbackButton(text="← Назад", payload=CB_BACK))
    kb.row(CallbackButton(text="Закрыть клавиатуру", payload=CB_CLOSE))
    return kb


def build_contact_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура с нативной кнопкой запроса контакта."""
    kb = InlineKeyboardBuilder()
    kb.row(RequestContactButton(text="Поделиться контактом"))
    kb.row(CallbackButton(text="← Назад", payload=CB_BACK))
    return kb


def build_geo_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура с нативной кнопкой запроса геолокации."""
    kb = InlineKeyboardBuilder()
    kb.row(RequestGeoLocationButton(text="Поделиться геолокацией"))
    kb.row(CallbackButton(text="← Назад", payload=CB_BACK))
    return kb


def main() -> None:
    """Демонстрация клавиатур через Bot API."""
    # Пример отправки клавиатуры пользователю.
    # В реальном боте user_id берётся из входящего обновления (update),
    # здесь для демонстрации читаем из переменной окружения.
    user_id = os.environ.get("MAX_USER_ID")
    if user_id is None:
        print(
            "Установите MAX_USER_ID для демонстрации отправки.\n"
            "Пример: MAX_USER_ID=12345 MAX_BOT_TOKEN=your_token python 03_keyboard_bot.py"
        )
        return

    uid = int(user_id)

    # 1. Отправляем сообщение с главным меню
    print("Отправка главного меню с inline-клавиатурой...")
    sent = bot.send_message(
        user_id=uid,
        text="Выберите действие:",
        attachments=[build_main_keyboard().as_markup()],
    )

    # 2. Получаем message_id отправленного сообщения для редактирования
    if sent and sent.message and sent.message.body:
        mid = sent.message.body.mid
        print(f"Сообщение отправлено, message_id: {mid}")

        # 3. Пример редактирования сообщения — заменяем на экран информации
        print("Редактирование сообщения — экран информации...")
        bot.edit_message(
            message_id=mid,
            text="Это бот-пример из документации maxapi.\nВерсия: 1.0.0",
            attachments=[build_info_keyboard().as_markup()],
        )

        # 4. Возврат к главному меню
        print("Возврат к главному меню...")
        bot.edit_message(
            message_id=mid,
            text="Выберите действие:",
            attachments=[build_main_keyboard().as_markup()],
        )

        # 5. Пример удаления клавиатуры — передаём пустой список attachments
        print("Удаление клавиатуры...")
        bot.edit_message(
            message_id=mid,
            text="Клавиатура убрана.",
            attachments=[],
        )
    else:
        print("Не удалось получить message_id для демонстрации редактирования.")

    print("Готово!")


if __name__ == "__main__":
    main()
