from typing import Any

from aiohttp import ClientTimeout


class DefaultConnectionProperties:
    """
    Класс для хранения параметров соединения по умолчанию для aiohttp-клиента.

    Args:
        timeout (float): Таймаут всего соединения в секундах (по умолчанию 5 * 30).
        sock_connect (int): Таймаут установки TCP-соединения в секундах (по умолчанию 30).
        **kwargs (Any): Дополнительные параметры, которые будут сохранены как есть.

    Attributes:
        timeout (ClientTimeout): Экземпляр aiohttp.ClientTimeout с заданными параметрами.
        kwargs (dict): Дополнительные параметры.
    """

    def __init__(
        self, timeout: float = 5 * 30, sock_connect: int = 30, **kwargs: Any
    ):
        """
        Инициализация параметров соединения.

        Args:
            timeout (float): Таймаут всего соединения в секундах.
            sock_connect (int): Таймаут установки TCP-соединения в секундах.
            **kwargs (Any): Дополнительные параметры.
        """
        self.timeout = ClientTimeout(total=timeout, sock_connect=sock_connect)
        self.kwargs = kwargs
