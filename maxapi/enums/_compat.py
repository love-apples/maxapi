"""Совместимость StrEnum для Python < 3.11.

TODO(pyupgrade): когда requires-python станет >=3.11,
  удалить этот модуль и заменить все
  ``from ._compat import StrEnum``
  на ``from enum import StrEnum``.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import Self

if sys.version_info >= (3, 11):  # pragma: no cover
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        """Backport StrEnum для Python 3.10."""

        @staticmethod
        def _generate_next_value_(
            name: str,
            start: int,
            count: int,
            last_values: list,
        ) -> str:
            return name.lower()

        def __new__(cls, value: str) -> Self:
            if not isinstance(value, str):
                msg = f"{value!r} is not a string"
                raise TypeError(msg)
            member = str.__new__(cls, value)
            member._value_ = value
            return member


__all__ = ["StrEnum"]
