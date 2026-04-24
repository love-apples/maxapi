from __future__ import annotations

import math
from time import monotonic


class TTLTracker:
    """
    Управляет временем жизни контекста.
    """

    def __init__(self, ttl: float | None = None) -> None:
        if ttl is not None and (not math.isfinite(ttl) or ttl <= 0):
            raise ValueError("ttl must be a positive finite number")
        self.ttl = ttl
        self._expires_at: float | None = None

    def touch(self) -> None:
        """
        Продлевает срок жизни после обращения к контексту.
        """
        if self.ttl is None:
            self._expires_at = None
            return
        self._expires_at = monotonic() + self.ttl

    def is_expired(self) -> bool:
        """
        Проверяет, истёк ли срок жизни.
        """
        return self._expires_at is not None and monotonic() >= self._expires_at

    def clear(self) -> None:
        """
        Сбрасывает срок жизни контекста.
        """
        self._expires_at = None
