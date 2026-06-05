"""
Deep linking через кнопку — создание ссылки и обработка payload.

Демонстрирует:
- create_start_link() — генерацию deep link MAX
- encode=True и decode_payload() для payload со спецсимволами
- CallbackButton — кнопку, которая предлагает создать ссылку
- Отправку deep link обычной ссылкой в тексте
- BotStarted.payload — обработку данных из deep link

Запуск:
    MAX_BOT_TOKEN=your_token python 15_deep_linking_bot.py
"""

import asyncio
import contextlib
import logging

with contextlib.suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv()

from maxapi import Bot, Dispatcher, F
from maxapi.filters.command import CommandStart
from maxapi.types.attachments.buttons.callback_button import CallbackButton
from maxapi.types.updates.bot_started import BotStarted
from maxapi.types.updates.message_callback import MessageCallback
from maxapi.types.updates.message_created import MessageCreated
from maxapi.utils.deep_linking import create_start_link, decode_payload
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()

CB_CREATE_DEEP_LINK = "create_deep_link"
DEEP_LINK_PAYLOAD = "source=button&promo=welcome"


def build_start_keyboard() -> list:
    """Клавиатура с предложением создать deep link."""
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(
            text="Создать deep link",
            payload=CB_CREATE_DEEP_LINK,
        )
    )
    return [builder.as_markup()]


@dp.message_created(CommandStart())
async def on_start(event: MessageCreated) -> None:
    """Показать кнопку, которая создаёт deep link."""
    await event.message.answer(
        text="Нажмите кнопку, чтобы получить deep link с payload.",
        attachments=build_start_keyboard(),
    )


@dp.message_callback(F.callback.payload == CB_CREATE_DEEP_LINK)
async def on_create_deep_link(event: MessageCallback) -> None:
    """Создать deep link и отправить его пользователю текстом."""
    username = bot.me.username if bot.me else None
    if username is None:
        await event.answer(notification="Не удалось получить username бота")
        return

    try:
        deep_link = create_start_link(
            username=username,
            payload=DEEP_LINK_PAYLOAD,
            encode=True,
        )
    except ValueError as e:
        log.info("Ошибка при создании deep link: %s", e)
        await event.answer(notification=str(e))
        return

    await event.answer()
    await event.message.answer(
        text=(
            "Deep link создан. Откройте ссылку: "
            f"{deep_link}\n\n"
            "После перехода бот получит payload в событии BotStarted."
        ),
    )


@dp.bot_started(F.payload)
async def on_deep_link_started(event: BotStarted) -> None:
    """Обработать запуск бота по deep link."""
    assert event.payload is not None
    payload = decode_payload(event.payload)

    await bot.send_message(
        chat_id=event.chat_id,
        text=f"Бот запущен по deep link.\nPayload: {payload}",
    )


@dp.bot_started()
async def on_plain_started(event: BotStarted) -> None:
    """Обработать обычное нажатие кнопки «Начать» без payload."""
    await bot.send_message(
        chat_id=event.chat_id,
        text="Напишите /start, чтобы создать deep link через кнопку.",
    )


async def main() -> None:
    """Точка входа."""
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
