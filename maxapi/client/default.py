from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientTimeout

# 429 (лимит запросов MAX) в дефолт не входит: включается явно через
# retry_on_statuses, чтобы не менять поведение существующих приложений.
DEFAULT_RETRY_STATUSES: tuple[int, ...] = (502, 503, 504)


@dataclass(frozen=True)
class RetryEvent:
    """Сведения о неудачной попытке перед повтором запроса.

    Attributes:
        status: HTTP-статус ответа; ``None`` при ошибке соединения.
        attempt: Номер неудачной попытки, начиная с 1.
        delay: Задержка в секундах перед следующей попыткой.
        body: Тело ответа сервера; пустая строка при ошибке
            соединения.
    """

    status: int | None
    attempt: int
    delay: float
    body: str = ""


#: Колбэк, вызываемый перед каждым повтором. Может быть синхронным
#: или асинхронным. Возврат ``False`` отменяет повтор: ошибка сразу
#: уходит вызывающему коду (``MaxApiError`` или ``MaxConnection``).
#: Исключение, поднятое самим колбэком, пробрасывается из
#: ``request()`` как есть.
RetryCallback = Callable[[RetryEvent], "Awaitable[bool | None] | bool | None"]


class DefaultConnectionProperties:
    """
    Класс для хранения параметров соединения по умолчанию для
    aiohttp-клиента.

    Args:
        timeout: Таймаут всего соединения в секундах
            (по умолчанию 5 * 30).
        sock_connect: Таймаут установки TCP-соединения в секундах
            (по умолчанию 30).
        max_retries: Максимальное количество повторных попыток
            при временных HTTP-ошибках (по умолчанию 3).
        retry_on_statuses: HTTP-статусы, при которых
            выполняется повторная попытка
            (по умолчанию 502, 503, 504). Чтобы повторять
            превышение лимита, добавьте 429:
            ``retry_on_statuses=(429, 502, 503, 504)``.
        retry_backoff_factor: Множитель для экспоненциальной
            задержки между попытками в секундах (по умолчанию 1.0).
            Верхние границы задержек: 1с, 2с, 4с; фактическая
            задержка случайна в диапазоне от 0 до границы
            (full jitter). Если ответ со статусом из
            ``retry_on_statuses`` содержит заголовок ``Retry-After``,
            ждём указанное в нём время, но не больше 60 с.
        on_retry: Колбэк перед каждым повтором (см. ``RetryEvent``).
            Позволяет притормозить остальные запросы приложения
            или вернуть ``False`` и отменить повтор. Исключение
            из колбэка пробрасывается из ``request()`` как есть.
        **kwargs: Дополнительные параметры, которые будут
            сохранены как есть.

    Attributes:
        timeout: Экземпляр aiohttp.ClientTimeout
            с заданными параметрами.
        max_retries: Максимальное количество повторных попыток.
        retry_on_statuses: HTTP-статусы для retry.
        retry_backoff_factor: Множитель задержки.
        on_retry: Колбэк перед повтором или None.
        kwargs: Дополнительные параметры.
    """

    def __init__(
        self,
        timeout: float = 5 * 30,
        sock_connect: int = 30,
        *,
        max_retries: int = 3,
        retry_on_statuses: tuple[int, ...] = DEFAULT_RETRY_STATUSES,
        retry_backoff_factor: float = 1.0,
        on_retry: RetryCallback | None = None,
        **kwargs: Any,
    ):
        """
        Инициализация параметров соединения.

        Args:
            timeout: Таймаут всего соединения в секундах.
            sock_connect: Таймаут установки TCP-соединения
                в секундах.
            max_retries: Максимальное количество повторных
                попыток при временных HTTP-ошибках.
            retry_on_statuses: HTTP-статусы
                для retry.
            retry_backoff_factor: Множитель задержки.
            on_retry: Колбэк перед каждым повтором.
            **kwargs: Дополнительные параметры.
        """
        self.timeout = ClientTimeout(total=timeout, sock_connect=sock_connect)
        if max_retries < 0:
            raise ValueError("max_retries должен быть >= 0")
        self.max_retries = max_retries
        self.retry_on_statuses = retry_on_statuses
        self.retry_backoff_factor = retry_backoff_factor
        self.on_retry = on_retry
        self.kwargs = kwargs
