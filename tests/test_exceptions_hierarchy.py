"""Тесты иерархии исключений maxapi.

Инвариант: любую ошибку либы можно поймать одним ``except MaxError``.
Тест защищает от регрессии — новое исключение, добавленное в
``maxapi.exceptions.__all__`` без наследования от ``MaxError``,
уронит этот тест.
"""

from __future__ import annotations

import inspect

import maxapi.exceptions as exc_module
from maxapi.exceptions import MaxApiError, MaxError


def _public_exception_classes() -> list[tuple[str, type[BaseException]]]:
    classes: list[tuple[str, type[BaseException]]] = []
    for name in exc_module.__all__:
        obj = getattr(exc_module, name)
        if inspect.isclass(obj) and issubclass(obj, BaseException):
            classes.append((name, obj))
    return classes


def test_public_exceptions_are_present():
    """__all__ не пуст — иначе последующие проверки бесполезны."""
    classes = _public_exception_classes()
    assert classes, "maxapi.exceptions.__all__ не содержит исключений"


def test_all_public_exceptions_inherit_from_max_error():
    """Все публичные исключения либы наследуются от MaxError."""
    non_max = [
        name
        for name, cls in _public_exception_classes()
        if cls is not MaxError and not issubclass(cls, MaxError)
    ]
    assert not non_max, (
        f"Эти исключения не наследуются от MaxError: {non_max}. "
        "Добавь MaxError в базовые классы или убери из публичного API."
    )


def test_max_error_is_exception_subclass():
    """MaxError остаётся совместим с обычным ``except Exception``."""
    assert issubclass(MaxError, Exception)


def test_except_max_error_catches_any_lib_error():
    """``except MaxError`` действительно ловит конкретные подклассы."""
    try:
        raise MaxApiError(code=500, raw={"x": 1})
    except MaxError as e:
        assert isinstance(e, MaxApiError)
        assert e.code == 500
        assert e.raw == {"x": 1}
    else:
        raise AssertionError("MaxApiError не был пойман как MaxError")


def test_max_api_error_dataclass_contract_preserved():
    """Смена базы на MaxError не сломала dataclass-контракт MaxApiError."""
    err = MaxApiError(code=418, raw="teapot")
    assert err.code == 418
    assert err.raw == "teapot"
    assert isinstance(err, MaxError)
