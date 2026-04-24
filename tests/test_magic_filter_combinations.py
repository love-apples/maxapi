"""Тесты комбинаций MagicFilter (F), описанных в docs/guides/filters.md.

Покрывают:
- одиночное сравнение (==)
- OR с правильными скобками: (F.x == "a") | (F.x == "b")
- AND с правильными скобками: F.x & (F.y == val)
- отрицание: ~F.x
- .in_() для множественных значений
- демонстрацию ошибки при отсутствии скобок (приоритет | выше ==)
- отсутствие ложных предупреждений при BaseFilter | F.x
"""

import warnings
from types import SimpleNamespace

import pytest
from maxapi import F
from maxapi.filters import filter_attrs
from maxapi.filters.filter import BaseFilter

# ---------------------------------------------------------------------------
# Вспомогательные фабрики объектов-заглушек
# ---------------------------------------------------------------------------


def _callback_event(payload: str):
    """Объект с аттрибутом callback.payload."""
    return SimpleNamespace(callback=SimpleNamespace(payload=payload))


def _message_event(
    *,
    text: str | None = None,
    chat_type=None,
    attachments=None,
):
    """Объект с аттрибутом message.body.text / chat.type / body.attachments."""
    return SimpleNamespace(
        message=SimpleNamespace(
            body=SimpleNamespace(text=text, attachments=attachments),
            chat=SimpleNamespace(type=chat_type),
        )
    )


# ---------------------------------------------------------------------------
# Одиночное сравнение (==) — базовый случай
# ---------------------------------------------------------------------------


class TestSingleEquality:
    """Одиночный фильтр F.x == value."""

    def test_match(self):
        """Фильтр совпадает при правильном значении."""
        event = _callback_event("ru")
        assert filter_attrs(event, F.callback.payload == "ru") is True

    def test_no_match(self):
        """Фильтр не срабатывает при другом значении."""
        event = _callback_event("de")
        assert filter_attrs(event, F.callback.payload == "ru") is False


# ---------------------------------------------------------------------------
# OR-комбинация с правильными скобками
# ---------------------------------------------------------------------------


class TestOrCombination:
    """(F.x == "a") | (F.x == "b") — скобки расставлены верно."""

    def test_first_value_matches(self):
        """Срабатывает на первое значение."""
        event = _callback_event("ru")
        f = (F.callback.payload == "ru") | (F.callback.payload == "en")
        assert filter_attrs(event, f) is True

    def test_second_value_matches(self):
        """Срабатывает на второе значение."""
        event = _callback_event("en")
        f = (F.callback.payload == "ru") | (F.callback.payload == "en")
        assert filter_attrs(event, f) is True

    def test_neither_value_matches(self):
        """Не срабатывает на стороннее значение."""
        event = _callback_event("de")
        f = (F.callback.payload == "ru") | (F.callback.payload == "en")
        assert filter_attrs(event, f) is False


# ---------------------------------------------------------------------------
# OR без скобок — предупреждение + демонстрация неверного результата
# ---------------------------------------------------------------------------


class TestOrWithoutParenthesesBug:
    """F.x == "a" | F.x == "b" — скобки ОТСУТСТВУЮТ.

    Из-за более высокого приоритета | по сравнению с ==, выражение парсится
    Python как: F.x == ("a" | F.x) == "b"  — chained comparison без скобок.

    _SafeMagicFilter перехватывает вызов __ror__ с нефильтровым аргументом
    слева и эмитирует UserWarning в момент создания выражения.
    """

    def test_wrong_form_emits_warning(self):
        """При создании выражения без скобок выдаётся UserWarning."""
        with pytest.warns(UserWarning, match="приоритет"):
            # Эта строка создаёт неверный фильтр И должна выдать предупреждение
            _bad = F.callback.payload == "ru" | F.callback.payload == "en"

    def test_wrong_form_warning_contains_hint(self):
        """Текст предупреждения содержит правильную форму записи."""
        with pytest.warns(UserWarning, match=r"\(F\.x == .+\) \|"):
            _bad = F.callback.payload == "ru" | F.callback.payload == "en"

    def test_wrong_form_does_not_match_first_value(self):
        """Неверная форма НЕ срабатывает, даже когда значение совпадает."""
        event = _callback_event("ru")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            wrong_filter = (
                F.callback.payload == "ru" | F.callback.payload == "en"
            )
        result = filter_attrs(event, wrong_filter)
        assert result is False, (
            "Форма без скобок возвращает неверный результат — "
            "используйте (F.x == 'a') | (F.x == 'b')"
        )

    def test_wrong_form_does_not_match_second_value(self):
        """Неверная форма НЕ срабатывает и для второго значения."""
        event = _callback_event("en")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            wrong_filter = (
                F.callback.payload == "ru" | F.callback.payload == "en"
            )
        result = filter_attrs(event, wrong_filter)
        assert result is False


# ---------------------------------------------------------------------------
# .in_() — предпочтительный способ для множества значений
# ---------------------------------------------------------------------------


class TestInFilter:
    """F.x.in_(set) — удобный способ вместо цепочки OR."""

    def test_first_value_matches(self):
        """Срабатывает на первое значение из множества."""
        event = _callback_event("ru")
        f = F.callback.payload.in_({"ru", "en"})
        assert filter_attrs(event, f) is True

    def test_second_value_matches(self):
        """Срабатывает на второе значение из множества."""
        event = _callback_event("en")
        f = F.callback.payload.in_({"ru", "en"})
        assert filter_attrs(event, f) is True

    def test_value_not_in_set(self):
        """Не срабатывает на значение вне множества."""
        event = _callback_event("de")
        f = F.callback.payload.in_({"ru", "en"})
        assert filter_attrs(event, f) is False

    def test_in_with_list(self):
        """Работает и со списком, не только с set."""
        event = _callback_event("ru")
        f = F.callback.payload.in_(["ru", "en"])
        assert filter_attrs(event, f) is True


# ---------------------------------------------------------------------------
# AND-комбинация с правильными скобками
# ---------------------------------------------------------------------------


class TestAndCombination:
    """F.x & (F.y == val) — & имеет более высокий приоритет, чем ==."""

    def test_both_conditions_match(self):
        """Срабатывает, когда оба условия выполнены."""
        from maxapi.enums.chat_type import ChatType

        event = _message_event(text="привет", chat_type=ChatType.DIALOG)
        f = F.message.body.text & (F.message.chat.type == ChatType.DIALOG)
        assert filter_attrs(event, f) is True

    def test_first_condition_fails(self):
        """Не срабатывает, если текст отсутствует."""
        from maxapi.enums.chat_type import ChatType

        event = _message_event(text=None, chat_type=ChatType.DIALOG)
        f = F.message.body.text & (F.message.chat.type == ChatType.DIALOG)
        assert filter_attrs(event, f) is False

    def test_second_condition_fails(self):
        """Не срабатывает, если тип чата не совпадает."""
        from maxapi.enums.chat_type import ChatType

        event = _message_event(text="привет", chat_type="group")
        f = F.message.body.text & (F.message.chat.type == ChatType.DIALOG)
        assert filter_attrs(event, f) is False


# ---------------------------------------------------------------------------
# NOT-фильтр (~F.x)
# ---------------------------------------------------------------------------


class TestNotFilter:
    """~F.x — отрицание: срабатывает, когда значение falsy/отсутствует."""

    def test_negation_when_field_is_falsy(self):
        """Срабатывает, когда поле None или пустое."""
        event = _message_event(text=None)
        assert filter_attrs(event, ~F.message.body.text) is True

    def test_negation_when_field_is_truthy(self):
        """Не срабатывает, когда поле заполнено."""
        event = _message_event(text="hello")
        assert filter_attrs(event, ~F.message.body.text) is False


# ---------------------------------------------------------------------------
# Проверка на истинность (без ==)
# ---------------------------------------------------------------------------


class TestTruthyOrFilter:
    """F.x | F.y — OR по истинности, скобки не нужны."""

    def test_first_field_truthy(self):
        """Срабатывает, когда заполнено первое поле."""
        event = _message_event(text="hello", attachments=None)
        f = F.message.body.text | F.message.body.attachments
        assert filter_attrs(event, f) is True

    def test_second_field_truthy(self):
        """Срабатывает, когда заполнено второе поле."""
        event = _message_event(text=None, attachments=["file"])
        f = F.message.body.text | F.message.body.attachments
        assert filter_attrs(event, f) is True

    def test_both_fields_falsy(self):
        """Не срабатывает, когда оба поля пусты."""
        event = _message_event(text=None, attachments=None)
        f = F.message.body.text | F.message.body.attachments
        assert filter_attrs(event, f) is False


# ---------------------------------------------------------------------------
# Ложные срабатывания: BaseFilter | F.x не должен вызывать предупреждение
# ---------------------------------------------------------------------------


class TestNoFalsePositiveWithBaseFilter:
    """BaseFilter слева от '|' не является ошибкой приоритета.

    _SafeMagicFilter должен НЕ выдавать предупреждение, если слева стоит
    BaseFilter (или MagicFilter). Предупреждение предназначено только для
    нефильтровых значений (строки, числа и т.д.).

    NB: комбинирование BaseFilter и MagicFilter через | в коде декоратора
    не имеет смысла (фильтры передаются отдельными аргументами), но это не
    должно приводить к ложным предупреждениям об ошибке приоритета.
    """

    def test_base_filter_or_magic_filter_no_warning(self):
        """BaseFilter() | F.x не вызывает UserWarning."""

        class AlwaysTrue(BaseFilter):
            async def __call__(self, event):
                return True

        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            # Не должно бросить исключение (нет UserWarning)
            _ = AlwaysTrue() | F.callback.payload

    def test_magic_filter_or_magic_filter_no_warning(self):
        """(F.x == "a") | (F.x == "b") не вызывает UserWarning."""
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            _ = (F.callback.payload == "yes") | (F.callback.payload == "no")
