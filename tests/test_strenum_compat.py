"""Тесты на StrEnum-совместимость из maxapi.enums._compat."""

from enum import auto, unique

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
    import pytest

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
