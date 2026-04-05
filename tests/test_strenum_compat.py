"""Тесты на StrEnum-совместимость из maxapi.enums._compat."""

from enum import auto, unique

import pytest
from maxapi.enums._compat import StrEnum


class _SampleEnum(StrEnum):
    FOO_BAR = auto()
    BAZ = auto()


def test_auto_generates_lowercase_name():
    """auto() должен генерировать name.lower()."""
    assert _SampleEnum.FOO_BAR == "foo_bar"
    assert _SampleEnum.BAZ == "baz"


def test_members_are_str_instances():
    """Члены StrEnum должны быть экземплярами str."""
    assert isinstance(_SampleEnum.FOO_BAR, str)
    assert isinstance(_SampleEnum.BAZ, str)


def test_value_equals_str():
    """.value тоже должен быть строкой."""
    assert _SampleEnum.FOO_BAR.value == "foo_bar"


def test_unique_decorator_rejects_duplicates():
    """@unique должен работать с compat StrEnum."""
    with pytest.raises(ValueError, match="duplicate"):

        @unique
        class _Bad(StrEnum):
            A = "x"
            B = "x"


def test_explicit_value_preserved():
    """Явно заданное значение не должно заменяться."""

    class _Explicit(StrEnum):
        HELLO = "world"

    assert _Explicit.HELLO == "world"
    assert _Explicit.HELLO.value == "world"


def test_non_string_value_raises_type_error():
    """Нестроковое значение должно вызывать TypeError."""
    with pytest.raises(TypeError, match="is not a string"):

        class _Bad(StrEnum):
            X = 1


def test_str_returns_value():
    """str(member) должен возвращать значение, а не 'ClassName.MEMBER'.

    В stdlib 3.11+ это обеспечивает ReprEnum → str.__str__.
    """
    assert str(_SampleEnum.FOO_BAR) == "foo_bar"
    assert str(_SampleEnum.BAZ) == "baz"


def test_repr_is_standard_enum_repr():
    """repr(member) должен быть стандартным Enum repr."""
    assert repr(_SampleEnum.FOO_BAR) == "<_SampleEnum.FOO_BAR: 'foo_bar'>"


def test_format_returns_value():
    """format(member) и f-строки должны возвращать значение."""
    assert format(_SampleEnum.FOO_BAR) == "foo_bar"
    assert f"{_SampleEnum.BAZ}" == "baz"
