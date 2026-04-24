"""
Типизированные callback payloads — каталог товаров с навигацией.

Демонстрирует:
- Определение классов CallbackPayload с prefix
- Упаковку payload через .pack() и распаковку через .unpack()
- Фильтрацию callback-событий через MyPayload.filter()
- Получение типизированного объекта payload в хендлере
- Каталог товаров: категории → товары → детали товара
- Кнопку «Назад» с сохранением контекста навигации
- event.answer() для подтверждения callback (убирает «часики»)
- SenderAction перед отображением «тяжёлых» экранов

Аналог Telegram: aiogram CallbackData с prefix

Запуск:
    MAX_BOT_TOKEN=your_token python 10_callback_payload_bot.py
"""

import asyncio
import logging

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass
from maxapi import Bot, Dispatcher, F
from maxapi.enums.sender_action import SenderAction
from maxapi.filters.callback_payload import CallbackPayload
from maxapi.filters.command import CommandStart
from maxapi.types.attachments.buttons.callback_button import CallbackButton
from maxapi.types.updates.bot_started import BotStarted
from maxapi.types.updates.message_callback import MessageCallback
from maxapi.types.updates.message_created import MessageCreated
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)

bot = Bot()
dp = Dispatcher()

# ---------------------------------------------------------------------------
# Данные каталога
# ---------------------------------------------------------------------------

CATEGORIES: dict[str, str] = {
    "1": "Электроника",
    "2": "Одежда",
    "3": "Книги",
}

ITEMS: dict[str, dict[str, str]] = {
    "1": {"101": "Смартфон XY", "102": "Ноутбук Pro", "103": "Наушники Z"},
    "2": {"201": "Футболка", "202": "Джинсы", "203": "Куртка"},
    "3": {"301": "Чистый код", "302": "Python Cookbook", "303": "Алгоритмы"},
}

PRICES: dict[str, str] = {
    "101": "29 990 ₽",
    "102": "89 990 ₽",
    "103": "4 990 ₽",
    "201": "990 ₽",
    "202": "2 990 ₽",
    "203": "5 990 ₽",
    "301": "890 ₽",
    "302": "1 290 ₽",
    "303": "1 490 ₽",
}


# ---------------------------------------------------------------------------
# Payload-классы
# ---------------------------------------------------------------------------


class CategoryPayload(CallbackPayload, prefix="cat"):
    """Payload для выбора категории каталога."""

    category_id: str


class ItemPayload(CallbackPayload, prefix="item"):
    """Payload для выбора товара внутри категории."""

    category_id: str
    item_id: str


class BuyPayload(CallbackPayload, prefix="buy"):
    """Payload для кнопки «Купить» на карточке товара."""

    item_id: str
    category_id: str  # сохраняем для кнопки «Назад»


class BackToCategoriesPayload(CallbackPayload, prefix="back_cats"):
    """Payload для возврата к списку категорий."""


class BackToItemsPayload(CallbackPayload, prefix="back_items"):
    """Payload для возврата к списку товаров категории."""

    category_id: str


# ---------------------------------------------------------------------------
# Вспомогательные функции построения клавиатур
# ---------------------------------------------------------------------------


def build_categories_keyboard() -> list:
    """Построить клавиатуру со списком категорий."""
    builder = InlineKeyboardBuilder()
    for cat_id, cat_name in CATEGORIES.items():
        payload = CategoryPayload(category_id=cat_id).pack()
        builder.row(CallbackButton(text=cat_name, payload=payload))
    return [builder.as_markup()]


def build_items_keyboard(category_id: str) -> list:
    """Построить клавиатуру со списком товаров выбранной категории."""
    builder = InlineKeyboardBuilder()
    items = ITEMS.get(category_id, {})
    for item_id, item_name in items.items():
        payload = ItemPayload(category_id=category_id, item_id=item_id).pack()
        builder.row(CallbackButton(text=item_name, payload=payload))

    back_payload = BackToCategoriesPayload().pack()
    builder.row(CallbackButton(text="← Категории", payload=back_payload))
    return [builder.as_markup()]


def build_detail_keyboard(category_id: str, item_id: str) -> list:
    """Построить клавиатуру страницы детального просмотра товара."""
    builder = InlineKeyboardBuilder()

    # Кнопка «Купить» (для демонстрации — просто уведомление)
    buy_payload = BuyPayload(item_id=item_id, category_id=category_id).pack()
    builder.row(CallbackButton(text="Купить", payload=buy_payload))

    # Кнопка «Назад» возвращает в список товаров категории
    back_payload = BackToItemsPayload(category_id=category_id).pack()
    builder.row(CallbackButton(text="← Назад", payload=back_payload))
    return [builder.as_markup()]


# ---------------------------------------------------------------------------
# Хендлеры команд
# ---------------------------------------------------------------------------


@dp.bot_started()
async def on_bot_started(event: BotStarted) -> None:
    """Приветствие и вход в каталог."""
    await bot.send_message(
        user_id=event.user.user_id,
        text=(
            "Добро пожаловать в магазин! "
            "Напишите /start для открытия каталога."
        ),
    )


@dp.message_created(CommandStart())
async def on_start(event: MessageCreated) -> None:
    """Показать главное меню каталога."""
    await event.message.answer(
        text="Выберите категорию:",
        attachments=build_categories_keyboard(),
    )


# ---------------------------------------------------------------------------
# Хендлеры callback: выбор категории
# ---------------------------------------------------------------------------


@dp.message_callback(CategoryPayload.filter())
async def on_category(
    event: MessageCallback, payload: CategoryPayload
) -> None:
    """Пользователь выбрал категорию — показываем список товаров."""
    # Подтверждаем callback, чтобы убрать «часики» на кнопке
    await event.answer()

    cat_name = CATEGORIES.get(payload.category_id, "Неизвестная категория")

    chat_id = event.message.recipient.chat_id if event.message else None
    if chat_id:
        await bot.send_action(chat_id=chat_id, action=SenderAction.TYPING_ON)

    await bot.send_message(
        chat_id=event.message.recipient.chat_id if event.message else None,
        user_id=event.callback.user.user_id,
        text=f"Категория: {cat_name}\nВыберите товар:",
        attachments=build_items_keyboard(payload.category_id),
    )


# ---------------------------------------------------------------------------
# Хендлеры callback: выбор товара
# ---------------------------------------------------------------------------


@dp.message_callback(ItemPayload.filter())
async def on_item(event: MessageCallback, payload: ItemPayload) -> None:
    """Пользователь выбрал товар — показываем карточку с кнопками."""
    await event.answer()

    items = ITEMS.get(payload.category_id, {})
    item_name = items.get(payload.item_id, "Неизвестный товар")
    price = PRICES.get(payload.item_id, "цена не указана")

    chat_id = event.message.recipient.chat_id if event.message else None
    if chat_id:
        await bot.send_action(chat_id=chat_id, action=SenderAction.TYPING_ON)

    await bot.send_message(
        chat_id=chat_id,
        user_id=event.callback.user.user_id,
        text=f"Товар: {item_name}\nЦена: {price}",
        attachments=build_detail_keyboard(
            payload.category_id, payload.item_id
        ),
    )


# ---------------------------------------------------------------------------
# Хендлеры callback: детали товара (кнопка «Купить»)
# ---------------------------------------------------------------------------


@dp.message_callback(BuyPayload.filter())
async def on_detail(event: MessageCallback, payload: BuyPayload) -> None:
    """Обработка нажатия «Купить»."""
    items_all = ITEMS.get(payload.category_id, {})
    item_name = items_all.get(payload.item_id, "товар")
    # Уведомление появляется поверх экрана (всплывающее)
    await event.answer(notification=f"Заказ на «{item_name}» оформлен!")


# ---------------------------------------------------------------------------
# Хендлеры callback: кнопки «Назад»
# ---------------------------------------------------------------------------


@dp.message_callback(BackToCategoriesPayload.filter())
async def on_back_to_categories(event: MessageCallback) -> None:
    """Возврат к списку категорий."""
    await event.answer()
    await bot.send_message(
        chat_id=event.message.recipient.chat_id if event.message else None,
        user_id=event.callback.user.user_id,
        text="Выберите категорию:",
        attachments=build_categories_keyboard(),
    )


@dp.message_callback(BackToItemsPayload.filter())
async def on_back_to_items(
    event: MessageCallback, payload: BackToItemsPayload
) -> None:
    """Возврат к списку товаров категории."""
    await event.answer()

    cat_name = CATEGORIES.get(payload.category_id, "Категория")
    await bot.send_message(
        chat_id=event.message.recipient.chat_id if event.message else None,
        user_id=event.callback.user.user_id,
        text=f"Категория: {cat_name}\nВыберите товар:",
        attachments=build_items_keyboard(payload.category_id),
    )


# ---------------------------------------------------------------------------
# Обработка неизвестных callback (fallback)
# ---------------------------------------------------------------------------


@dp.message_callback(F.callback.payload)
async def on_unknown_callback(event: MessageCallback) -> None:
    """Неизвестный payload — сообщаем пользователю."""
    await event.answer(notification="Действие не поддерживается.")


async def main() -> None:
    """Точка входа."""
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
