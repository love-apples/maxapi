from typing import Any

from aiohttp import ClientTimeout

DEFAULT_RETRY_STATUSES: tuple[int, ...] = (502, 503, 504)


class DefaultConnectionProperties:
    """
    Класс для хранения параметров соединения по умолчанию для
    aiohttp-клиента.

    Args:
        timeout (float): Таймаут всего соединения в секундах
            (по умолчанию 5 * 30).
        sock_connect (int): Таймаут установки TCP-соединения в секундах
            (по умолчанию 30).
        max_retries (int): Максимальное количество повторных попыток
            при серверных ошибках (по умолчанию 3).
        retry_on_statuses (tuple[int, ...]): HTTP-статусы, при которых
            выполняется повторная попытка
            (по умолчанию 502, 503, 504).
        retry_backoff_factor (float): Множитель для экспоненциальной
            задержки между попытками в секундах
            (по умолчанию 1.0, задержки: 1с, 2с, 4с).
        **kwargs (Any): Дополнительные параметры, которые будут
            сохранены как есть.

    Attributes:
        timeout (ClientTimeout): Экземпляр aiohttp.ClientTimeout
            с заданными параметрами.
        max_retries (int): Максимальное количество повторных попыток.
        retry_on_statuses (tuple[int, ...]): HTTP-статусы для retry.
        retry_backoff_factor (float): Множитель задержки.
        kwargs (dict): Дополнительные параметры.
    """

    def __init__(
        self,
        timeout: float = 5 * 30,
        sock_connect: int = 30,
        *,
        max_retries: int = 3,
        retry_on_statuses: tuple[int, ...] = DEFAULT_RETRY_STATUSES,
        retry_backoff_factor: float = 1.0,
        **kwargs: Any,
    ):
        """
        Инициализация параметров соединения.

        Args:
            timeout (float): Таймаут всего соединения в секундах.
            sock_connect (int): Таймаут установки TCP-соединения
                в секундах.
            max_retries (int): Максимальное количество повторных
                попыток при серверных ошибках.
            retry_on_statuses (tuple[int, ...]): HTTP-статусы
                для retry.
            retry_backoff_factor (float): Множитель задержки.
            **kwargs (Any): Дополнительные параметры.
        """
        self.timeout = ClientTimeout(total=timeout, sock_connect=sock_connect)
        if max_retries < 0:
            raise ValueError("max_retries должен быть >= 0")
        self.max_retries = max_retries
        self.retry_on_statuses = retry_on_statuses
        self.retry_backoff_factor = retry_backoff_factor
        self.kwargs = kwargs
