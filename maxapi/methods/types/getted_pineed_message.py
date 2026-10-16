"""
Устаревший модуль-псевдоним.

.. deprecated::
    Модуль ``getted_pineed_message`` переименован в
    ``getted_pinned_message`` (исправлена опечатка). Импортируйте
    ``GettedPin`` из :mod:`maxapi.methods.types.getted_pinned_message`
    или из :mod:`maxapi.methods.types`.
"""

import warnings

from .getted_pinned_message import GettedPin

warnings.warn(
    "Модуль maxapi.methods.types.getted_pineed_message устарел "
    "(опечатка в имени). Используйте "
    "maxapi.methods.types.getted_pinned_message.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["GettedPin"]
