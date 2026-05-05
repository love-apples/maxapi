from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class InvalidToken(Exception): ...


class MaxConnection(Exception): ...


class MaxUploadFileFailed(Exception): ...


class MaxIconParamsException(Exception): ...


@dataclass(slots=True)
class MaxApiError(Exception):
    code: int
    raw: str | dict[str, Any]

    def __str__(self) -> str:
        return f"Ошибка от API: {self.code=} {self.raw=}"
