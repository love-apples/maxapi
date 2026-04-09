"""
FSM-бот — пошаговая форма регистрации на maxapi.

Демонстрирует:
- StatesGroup с именованными состояниями
- Переходы через context.set_state()
- Сохранение данных через context.update_data()
- Чтение данных через context.get_data()
- Отмену через /cancel с context.clear()
- Валидацию ввода (имя непустое, возраст — число 1–120)
- Inline-кнопки подтверждения в финальном шаге
- Обработку callback в определённом состоянии

Аналог ConversationHandler из python-telegram-bot.

Запуск:
    MAX_BOT_TOKEN=your_token python 04_fsm_bot.py
"""

import asyncio
import logging

from dotenv import load_dotenv
from maxapi import Bot, Dispatcher, F
from maxapi.context.base import BaseContext
from maxapi.context.state_machine import State, StatesGroup
from maxapi.filters.command import Command, CommandStart
from maxapi.types.attachments.buttons.callback_button import CallbackButton
from maxapi.types.updates.message_callback import MessageCallback
from maxapi.types.updates.message_created import MessageCreated
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

load_dotenv()
logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()

# ── Состояния формы ────────────────────────────────────────────────────────


class Registration(StatesGroup):
    """Состояния пошаговой формы регистрации."""

    waiting_name = State()  # Ожидаем ввод имени
    waiting_age = State()  # Ожидаем ввод возраста
    waiting_city = State()  # Ожидаем ввод города
    confirm = State()  # Ожидаем подтверждение


# ── Клавиатура подтверждения ───────────────────────────────────────────────


def build_confirm_keyboard() -> InlineKeyboardBuilder:
    """Кнопки «Подтвердить» и «Отмена» для финального шага."""
    kb = InlineKeyboardBuilder()
    kb.row(
        CallbackButton(text="Подтвердить", payload="confirm_yes"),
        CallbackButton(text="Начать заново", payload="confirm_no"),
    )
    return kb


# ── Команды ────────────────────────────────────────────────────────────────


@dp.message_created(CommandStart())
async def cmd_start(event: MessageCreated, context: BaseContext) -> None:
    """Начало регистрации — запрашиваем имя."""
    await context.clear()  # Сбрасываем предыдущее состояние, если было
    await context.set_state(Registration.waiting_name)
    await event.message.answer(
        "Добро пожаловать! Начнём регистрацию.\n\n"
        "Введите ваше имя (или /cancel для отмены):"
    )


@dp.message_created(Command("cancel"))
async def cmd_cancel(event: MessageCreated, context: BaseContext) -> None:
    """Отмена в любом состоянии — очищаем контекст."""
    current = await context.get_state()
    if current is None:
        await event.message.answer("Нет активного процесса для отмены.")
        return

    await context.clear()
    await event.message.answer(
        "Регистрация отменена. Напишите /start чтобы начать заново."
    )


# ── Обработчики шагов ──────────────────────────────────────────────────────


@dp.message_created(Registration.waiting_name, F.message.body.text)
async def step_name(event: MessageCreated, context: BaseContext) -> None:
    """Шаг 1: получаем имя, переходим к возрасту."""
    name = (
        (event.message.body.text or "").strip() if event.message.body else ""
    )

    # Валидация: имя не должно быть пустым
    if not name:
        await event.message.answer(
            "Имя не может быть пустым. Попробуйте ещё раз:"
        )
        return

    await context.update_data(name=name)
    await context.set_state(Registration.waiting_age)
    await event.message.answer(f"Отлично, {name}! Теперь введите ваш возраст:")


@dp.message_created(Registration.waiting_age, F.message.body.text)
async def step_age(event: MessageCreated, context: BaseContext) -> None:
    """Шаг 2: получаем возраст с валидацией, переходим к городу."""
    raw = (event.message.body.text or "").strip() if event.message.body else ""

    # Валидация: возраст — целое число от 1 до 120
    try:
        age = int(raw)
        if not (1 <= age <= 120):
            raise ValueError("out of range")
    except ValueError:
        await event.message.answer(
            "Введите корректный возраст (число от 1 до 120):"
        )
        return

    await context.update_data(age=age)
    await context.set_state(Registration.waiting_city)
    await event.message.answer("Из какого вы города?")


@dp.message_created(Registration.waiting_city, F.message.body.text)
async def step_city(event: MessageCreated, context: BaseContext) -> None:
    """Шаг 3: получаем город, показываем сводку для подтверждения."""
    city = (
        (event.message.body.text or "").strip() if event.message.body else ""
    )

    if not city:
        await event.message.answer("Название города не может быть пустым:")
        return

    await context.update_data(city=city)
    await context.set_state(Registration.confirm)

    # Собираем сводку
    data = await context.get_data()
    summary = (
        "Проверьте данные:\n\n"
        f"Имя: {data.get('name', '—')}\n"
        f"Возраст: {data.get('age', '—')}\n"
        f"Город: {data.get('city', '—')}\n\n"
        "Всё верно?"
    )
    await event.message.answer(
        text=summary,
        attachments=[build_confirm_keyboard().as_markup()],
    )


# ── Подтверждение через callback ───────────────────────────────────────────


@dp.message_callback(Registration.confirm)
async def step_confirm(event: MessageCallback, context: BaseContext) -> None:
    """Финальный шаг: подтверждение или перезапуск."""
    payload = event.callback.payload if event.callback else None

    if payload == "confirm_yes":
        data = await context.get_data()
        await context.clear()
        await event.message.edit(
            text=(
                "Регистрация завершена!\n\n"
                f"Имя: {data.get('name', '—')}\n"
                f"Возраст: {data.get('age', '—')}\n"
                f"Город: {data.get('city', '—')}"
            ),
            attachments=None,
        )

    elif payload == "confirm_no":
        await context.clear()
        await event.message.edit(
            text="Данные сброшены. Напишите /start для новой попытки.",
            attachments=None,
        )

    await event.answer()


async def main() -> None:
    """Точка входа."""
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
