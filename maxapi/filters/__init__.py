"""Фильтры и магический фильтр F для maxapi."""

import warnings
from typing import Any

from magic_filter import MagicFilter, MagicT

from .channel_post import ChannelPostFilter
from .contact import Contact, ContactFilter
from .filter import BaseFilter

_WRONG_OR_HINT = (
    "Возможная ошибка приоритета операторов: значение {value!r} стоит "
    "слева от '|'.\n"
    "Оператор '|' имеет более высокий приоритет, чем '==', поэтому\n"
    "  F.x == 'a' | F.x == 'b'\n"
    "парсится как:\n"
    "  F.x == ('a' | F.x) == 'b'  ← неверно\n"
    "Правильные формы:\n"
    "  (F.x == 'a') | (F.x == 'b')\n"
    "  F.x.in_({{'a', 'b'}})"
)

_WRONG_AND_HINT = (
    "Возможная ошибка приоритета операторов: значение {value!r} стоит "
    "слева от '&'.\n"
    "Оператор '&' имеет более высокий приоритет, чем '==', поэтому\n"
    "  F.x == 'a' & F.x == 'b'\n"
    "парсится как:\n"
    "  F.x == ('a' & F.x) == 'b'  ← неверно\n"
    "Правильная форма:\n"
    "  (F.x == 'a') & (F.x == 'b')"
)


class _SafeMagicFilter(MagicFilter):
    """MagicFilter с защитой от ошибок приоритета операторов.

    При написании ``F.x == 'a' | F.x == 'b'`` Python вычисляет
    ``'a' | F.x`` раньше ``==``, что приводит к вызову ``__ror__``
    с нефильтровым аргументом слева. Перехваченный вызов становится
    сигналом для выдачи предупреждения пользователю.
    """

    def __ror__(self: MagicT, other: Any) -> MagicT:  # type: ignore[override]
        """Перехватывает ``value | F.x`` и предупреждает о возможной ошибке.

        Предупреждение не выдаётся, если ``other`` является ``MagicFilter``
        или ``BaseFilter`` — оба типа являются допустимыми фильтрами,
        хотя комбинирование ``BaseFilter | MagicFilter`` через ``|`` и не
        имеет смысла в декораторах (фильтры следует передавать отдельными
        аргументами).
        """
        if not isinstance(other, (MagicFilter, BaseFilter)):
            warnings.warn(
                _WRONG_OR_HINT.format(value=other),
                UserWarning,
                stacklevel=2,
            )
        return super().__ror__(other)  # type: ignore[return-value]

    def __rand__(self: MagicT, other: Any) -> MagicT:  # type: ignore[override]
        """Перехватывает ``value & F.x`` и предупреждает о возможной ошибке.

        Предупреждение не выдаётся, если ``other`` является ``MagicFilter``
        или ``BaseFilter``.
        """
        if not isinstance(other, (MagicFilter, BaseFilter)):
            warnings.warn(
                _WRONG_AND_HINT.format(value=other),
                UserWarning,
                stacklevel=2,
            )
        return super().__rand__(other)  # type: ignore[return-value]


F = _SafeMagicFilter()

__all__ = [
    "BaseFilter",
    "ChannelPostFilter",
    "Contact",
    "ContactFilter",
    "F",
    "filter_attrs",
]


def filter_attrs(obj: object, *filters: MagicT) -> bool:
    """
    Применяет один или несколько фильтров MagicFilter к объекту.

    Args:
        obj (object): Объект, к которому применяются фильтры (например,
            event или message).
        *filters (MagicFilter): Один или несколько выражений MagicFilter.

    Returns:
        bool: True, если все фильтры возвращают True, иначе False.
    """

    try:
        return all(f.resolve(obj) for f in filters)
    except Exception:
        return False
