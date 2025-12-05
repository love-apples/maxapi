from dataclasses import dataclass


class InvalidToken(Exception): ...


class MaxConnection(Exception): ...


class MaxUploadFileFailed(Exception): ...


class MaxIconParamsException(Exception): ...


@dataclass(slots=True)
class MaxApiError(Exception):
    code: int
    raw: str

    def __str__(self) -> str:
        return f"Ошибка от API: {self.code=} {self.raw=}"
