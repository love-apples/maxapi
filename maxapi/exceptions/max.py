from dataclasses import dataclass
from typing import Any


class InvalidToken(Exception): ...


class MaxConnection(Exception): ...


class MaxUploadFileFailed(Exception): ...


class MaxIconParamsException(Exception): ...


@dataclass(slots=True)
class MaxApiError(Exception):
    """Ошибка, возвращённая API MAX.

    Attributes:
        code: HTTP-код ответа.
        raw: Сырой ответ от API (обычно dict из JSON).
    """

    code: int
    raw: Any

    def __str__(self) -> str:
        return f"Ошибка от API: {self.code=} {self.raw=}"
