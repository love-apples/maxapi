"""
Бот с клавиатурами — полный пример работы с inline-кнопками в maxapi.

Демонстрирует:
- InlineKeyboardBuilder — построитель inline-клавиатуры
- CallbackButton с payload-строкой
- LinkButton — кнопка-ссылка
- RequestContactButton — запрос контакта пользователя
- RequestGeoLocationButton — запрос геолокации
- Обработку MessageCallback
- event.answer() — обязательный acknowledgement колбэка
- Редактирование сообщения с новой клавиатурой через edit_message
- Удаление клавиатуры
- Навигацию кнопкой «Назад»

Аналог Telegram: InlineKeyboardMarkup, CallbackQueryHandler /
    aiogram InlineKeyboardBuilder

Запуск:
    MAX_BOT_TOKEN=your_token python 03_keyboard_bot.py
"""

import asyncio
import logging

from dotenv import load_dotenv
from maxapi import Bot, Dispatcher
from maxapi.filters.command import CommandStart
from maxapi.types.attachments.buttons.callback_button import CallbackButton
from maxapi.types.attachments.buttons.link_button import LinkButton
from maxapi.types.attachments.buttons.request_contact import (
    RequestContactButton,
)
from maxapi.types.attachments.buttons.request_geo_location_button import (
    RequestGeoLocationButton,
)
from maxapi.types.updates.message_callback import MessageCallback
from maxapi.types.updates.message_created import MessageCreated
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

load_dotenv()
logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()

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


@dp.message_created(CommandStart())
async def on_start(event: MessageCreated) -> None:
    """Отправляем главное меню при команде /start."""
    await event.message.answer(
        text="Выберите действие:",
        attachments=[build_main_keyboard().as_markup()],
    )


@dp.message_callback()
async def on_callback(event: MessageCallback) -> None:
    """Централизованный обработчик всех callback-нажатий.

    Важно: каждый callback ОБЯЗАТЕЛЬНО подтверждается через event.answer(),
    иначе кнопка будет «крутиться» у пользователя.
    """
    # Достаём payload; защита от None
    payload = event.callback.payload if event.callback else None
    if payload is None:
        await event.answer()
        return

    if payload == CB_INFO:
        await event.message.edit(
            text="Это бот-пример из документации maxapi.\nВерсия: 1.0.0",
            attachments=[build_info_keyboard().as_markup()],
        )

    elif payload == CB_CONTACT:
        await event.message.edit(
            text="Нажмите кнопку, чтобы поделиться контактом:",
            attachments=[build_contact_keyboard().as_markup()],
        )

    elif payload == CB_GEO:
        await event.message.edit(
            text="Нажмите кнопку, чтобы поделиться геолокацией:",
            attachments=[build_geo_keyboard().as_markup()],
        )

    elif payload in (CB_BACK, CB_MENU):
        # Возврат к главному меню
        await event.message.edit(
            text="Выберите действие:",
            attachments=[build_main_keyboard().as_markup()],
        )

    elif payload == CB_CLOSE:
        # Убираем клавиатуру, оставляем текст
        await event.message.edit(
            text="Клавиатура убрана. Напишите /start для повтора.",
            attachments=None,
        )

    # Обязательный ack — без него UI покажет ошибку
    await event.answer()


async def main() -> None:
    """Точка входа."""
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
