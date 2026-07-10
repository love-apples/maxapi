import warnings
from re import fullmatch
from typing import TYPE_CHECKING, cast
from urllib.parse import urlparse

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..types.chats import Chat

if TYPE_CHECKING:
    from ..bot import Bot


class GetChatByLink(BaseConnection):
    """
    Класс для получения информации о канале по публичной ссылке.

    .. deprecated:: 1.2.1
        Метод удалён из текущей OpenAPI-спецификации API MAX.
        Использование не рекомендуется.

    https://dev.max.ru/docs-api/methods/GET/chats/-chatLink-

    Attributes:
        link: Нормализованная публичная ссылка.
        PATTERN_LINK: Регулярное выражение для парсинга ссылки.
    """

    PATTERN_LINK: str = r"@?[a-zA-Z]+[a-zA-Z0-9-_]*"

    def __init__(self, bot: "Bot", link: str):
        warnings.warn(
            "GetChatByLink устарел и отсутствует в текущей "
            "OpenAPI-спецификации API MAX. "
            "Использование не рекомендуется.",
            DeprecationWarning,
            stacklevel=2,
        )

        super().__init__()
        self.bot = bot
        self.link = self._normalize_link(link)

        if fullmatch(self.PATTERN_LINK, self.link) is None:
            raise ValueError(f"link не соответствует {self.PATTERN_LINK!r}")

    @staticmethod
    def _normalize_link(link: str) -> str:
        value = link.strip()
        parsed = urlparse(value)

        if parsed.scheme or parsed.netloc:
            value = parsed.path.rstrip("/").rsplit("/", maxsplit=1)[-1]

        return value

    async def fetch(self) -> Chat:
        """
        Выполняет GET-запрос для получения данных канала по ссылке.

        Returns:
            Chat: Объект с информацией о чате.
        """

        bot = self._ensure_bot()

        response = await super().request(
            method=HTTPMethod.GET,
            path=ApiPath.CHATS.value + "/" + self.link,
            model=Chat,
            params=bot.params,
        )

        return cast(Chat, response)
