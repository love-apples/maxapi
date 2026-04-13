"""Тесты InlineKeyboardBuilder."""

from maxapi.enums.attachment import AttachmentType
from maxapi.types import (
    CallbackButton,
    ChatButton,
    ClipboardButton,
    LinkButton,
    RequestContactButton,
    RequestGeoLocationButton,
)
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder


def test_builder_init():
    """Тест инициализации билдера."""
    builder = InlineKeyboardBuilder()
    assert isinstance(builder.payload, list)
    assert len(builder.payload) == 1
    assert builder.payload[0] == []


def test_add_button():
    """Тест добавления кнопки."""
    builder = InlineKeyboardBuilder()
    button = CallbackButton(text="Test", payload="test_payload")

    builder.add(button)

    assert len(builder.payload[0]) == 1
    assert builder.payload[0][0] == button


def test_add_multiple_buttons():
    """Тест добавления нескольких кнопок в один ряд."""
    builder = InlineKeyboardBuilder()
    button1 = CallbackButton(text="Button 1", payload="payload1")
    button2 = LinkButton(text="Button 2", url="https://example.com")

    builder.add(button1)
    builder.add(button2)

    assert len(builder.payload[0]) == 2
    assert builder.payload[0][0] == button1
    assert builder.payload[0][1] == button2


def test_row_empty():
    """Тест создания нового ряда."""
    builder = InlineKeyboardBuilder()
    builder.add(CallbackButton(text="B1", payload="p1"))
    builder.row()

    assert len(builder.payload) == 2
    assert len(builder.payload[0]) == 1
    assert builder.payload[1] == []


def test_row_with_buttons():
    """Тест создания ряда с кнопками."""
    builder = InlineKeyboardBuilder()
    button1 = CallbackButton(text="Button 1", payload="payload1")
    button2 = CallbackButton(text="Button 2", payload="payload2")

    builder.row(button1, button2)

    assert len(builder.payload) == 1
    assert len(builder.payload[0]) == 2
    assert builder.payload[0][0] == button1
    assert builder.payload[0][1] == button2


def test_multiple_rows():
    """Тест создания нескольких рядов."""
    builder = InlineKeyboardBuilder()
    button1 = CallbackButton(text="Button 1", payload="payload1")
    button2 = CallbackButton(text="Button 2", payload="payload2")
    button3 = CallbackButton(text="Button 3", payload="payload3")

    builder.add(button1)
    builder.row(button2)
    builder.add(button3)

    assert len(builder.payload) == 2
    assert len(builder.payload[0]) == 1  # Первый ряд
    assert len(builder.payload[1]) == 2  # Второй ряд


def test_as_markup():
    """Тест преобразования в markup."""
    builder = InlineKeyboardBuilder()
    button = CallbackButton(text="Test", payload="test_payload")
    builder.add(button)

    markup = builder.as_markup()

    assert markup.type == AttachmentType.INLINE_KEYBOARD
    assert hasattr(markup, "payload")
    assert markup.payload.buttons == builder.payload  # type: ignore


def test_complex_keyboard():
    """Тест создания сложной клавиатуры."""
    builder = InlineKeyboardBuilder()

    # Первый ряд
    builder.add(CallbackButton(text="Button 1", payload="1"))
    builder.add(CallbackButton(text="Button 2", payload="2"))

    # Второй ряд
    builder.row(LinkButton(text="Link", url="https://example.com"))

    # Третий ряд
    builder.add(ChatButton(text="Chat", chat_title="Test Chat"))
    builder.add(RequestContactButton(text="Contact"))

    markup = builder.as_markup()

    assert len(markup.payload.buttons) == 2  # type: ignore
    assert len(markup.payload.buttons[0]) == 2  # type: ignore
    assert len(markup.payload.buttons[1]) == 3  # type: ignore


def test_all_button_types():
    """Тест всех типов кнопок."""
    builder = InlineKeyboardBuilder()

    builder.add(CallbackButton(text="Callback", payload="payload"))
    builder.add(ClipboardButton(text="Copy", payload="copied"))
    builder.row(LinkButton(text="Link", url="https://example.com"))
    builder.add(ChatButton(text="Chat", chat_title="Test"))
    builder.add(RequestContactButton(text="Contact"))
    builder.add(RequestGeoLocationButton(text="Location"))

    # MessageButton и OpenAppButton требуют дополнительные параметры

    markup = builder.as_markup()
    assert markup.type == AttachmentType.INLINE_KEYBOARD


def test_empty_keyboard():
    """Тест создания пустой клавиатуры."""
    builder = InlineKeyboardBuilder()

    markup = builder.as_markup()

    assert markup.type == AttachmentType.INLINE_KEYBOARD
    assert len(markup.payload.buttons) == 1  # type: ignore
    assert len(markup.payload.buttons[0]) == 0  # type: ignore
