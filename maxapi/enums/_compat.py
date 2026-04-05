"""Совместимость StrEnum для Python < 3.11.

TODO(pyupgrade): когда requires-python станет >=3.11,
  удалить этот модуль и заменить все
  ``from ._compat import StrEnum``
  на ``from enum import StrEnum``.
"""

import sys

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


__all__ = ["StrEnum"]
