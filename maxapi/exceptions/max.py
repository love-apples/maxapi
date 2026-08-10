from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import MaxError


class InvalidToken(MaxError): ...


class MaxConnection(MaxError): ...


class MaxUploadFileFailed(MaxError): ...


class MaxIconParamsException(MaxError): ...


@dataclass(slots=True)
class MaxApiError(MaxError):
    """Ошибка, пришедшая от сервера API Макса (не-2xx ответ)."""

    code: int
    raw: str | dict[str, Any]

    def __str__(self) -> str:
        return f"Ошибка от API: {self.code=} {self.raw=}"
