"""
Типизированные callback payloads — каталог товаров с навигацией.

Демонстрирует:
- Определение классов CallbackPayload с prefix
- Упаковку payload через .pack() и распаковку через .unpack()
- Фильтрацию callback-событий через MyPayload.filter()
- Каталог товаров: категории -> товары -> детали товара
- InlineKeyboardBuilder для построения навигации
- bot.send_message() для отправки сообщений с клавиатурой

Аналог Telegram: aiogram CallbackData с prefix

Запуск:
    MAX_BOT_TOKEN=your_token python 10_callback_payload_bot.py
"""

import contextlib
import os

# Опционально: загрузка .env, если установлен python-dotenv
with contextlib.suppress(ImportError):
    from dotenv import load_dotenv

    load_dotenv()
from maxapi import Bot
from maxapi.enums.sender_action import SenderAction
from maxapi.filters.callback_payload import CallbackPayload
from maxapi.types.attachments.buttons.callback_button import CallbackButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

bot = Bot()

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
# Демонстрация
# ---------------------------------------------------------------------------


def main() -> None:
    """Демонстрация типизированных callback payloads через Bot API."""
    # В реальном боте user_id берётся из входящего обновления (update),
    # здесь для демонстрации читаем из переменной окружения.
    user_id = os.environ.get("MAX_USER_ID")
    if user_id is None:
        print(
            "Установите MAX_USER_ID для демонстрации отправки.\n"
            "Пример: MAX_USER_ID=12345 MAX_BOT_TOKEN=your_token python 10_callback_payload_bot.py"
        )
        return

    uid = int(user_id)

    # ── 1. Демонстрация упаковки payload ─────────────────────────────────
    print("=== Демонстрация CallbackPayload ===\n")

    # Упаковка payload
    cat_payload = CategoryPayload(category_id="1")
    packed = cat_payload.pack()
    print(f"CategoryPayload(category_id='1').pack() = '{packed}'")

    # Распаковка payload
    unpacked = CategoryPayload.unpack(packed)
    print(f"CategoryPayload.unpack('{packed}') = {unpacked}")
    print(f"  category_id = {unpacked.category_id}")

    # ── 2. Отправка каталога с inline-клавиатурой ────────────────────────
    print("\nОтправка каталога категорий...")
    bot.send_action(chat_id=uid, action=SenderAction.TYPING_ON)

    sent = bot.send_message(
        user_id=uid,
        text="Выберите категорию:",
        attachments=build_categories_keyboard(),
    )
    if sent and sent.message and sent.message.body:
        mid = sent.message.body.mid
        print(f"Каталог отправлен, message_id: {mid}")

        # ── 3. Редактирование — показ товаров категории ──────────────────
        category_id = "1"
        cat_name = CATEGORIES[category_id]
        print(f"\nРедактирование — список товаров категории «{cat_name}»...")
        bot.edit_message(
            message_id=mid,
            text=f"Категория: {cat_name}\nВыберите товар:",
            attachments=build_items_keyboard(category_id),
        )

        # ── 4. Редактирование — карточка товара ──────────────────────────
        item_id = "101"
        item_name = ITEMS[category_id][item_id]
        price = PRICES[item_id]
        print(f"\nРедактирование — карточка товара «{item_name}»...")
        bot.edit_message(
            message_id=mid,
            text=f"Товар: {item_name}\nЦена: {price}",
            attachments=build_detail_keyboard(category_id, item_id),
        )

        # ── 5. Возврат к категориям ──────────────────────────────────────
        print("\nВозврат к списку категорий...")
        bot.edit_message(
            message_id=mid,
            text="Выберите категорию:",
            attachments=build_categories_keyboard(),
        )
    else:
        print("Не удалось получить message_id для демонстрации навигации.")

    print("\nГотово!")


if __name__ == "__main__":
    main()
