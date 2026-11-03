import warnings
from datetime import datetime
from typing import TYPE_CHECKING, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..types.message import Messages
from ..utils.time import to_ms

if TYPE_CHECKING:
    from ..bot import Bot


class GetMessages(BaseConnection):
    """
    Класс для получения сообщений из чата через API.

    https://dev.max.ru/docs-api/methods/GET/messages

    Attributes:
        bot: Экземпляр бота.
        chat_id: Идентификатор чата.
        message_ids: Фильтр по идентификаторам сообщений.
        from_time: Начальная метка в миллисекундах. Устарело,
            используйте after.
        to_time: Конечная метка в миллисекундах. Устарело,
            используйте before.
        count: Максимальное число сообщений.
        before: Конечная временная метка в миллисекундах.
        after: Начальная временная метка в миллисекундах.
    """

    def __init__(
        self,
        bot: "Bot",
        chat_id: int | None = None,
        message_ids: list[str] | None = None,
        from_time: datetime | int | None = None,
        to_time: datetime | int | None = None,
        count: int | None = 50,
        *,
        before: datetime | int | None = None,
        after: datetime | int | None = None,
    ):
        if count is not None and not (1 <= count <= 100):
            raise ValueError("count не должен быть меньше 1 или больше 100")

        bounds = (
            (from_time, after, "from_time", "after"),
            (to_time, before, "to_time", "before"),
        )
        for legacy, current, legacy_name, current_name in bounds:
            if legacy is not None and current is not None:
                raise ValueError(
                    "Передайте только один из параметров: "
                    f"{legacy_name} или {current_name}"
                )

        has_chat_id = chat_id is not None
        has_message_ids = bool(message_ids)
        if has_chat_id == has_message_ids:
            raise ValueError(
                "Нужно передать ровно один из параметров: "
                "chat_id или message_ids"
            )

        if from_time is not None:
            warnings.warn(
                "Параметр from_time устарел, используйте after.",
                DeprecationWarning,
                stacklevel=4,
            )
        if to_time is not None:
            warnings.warn(
                "Параметр to_time устарел, используйте before.",
                DeprecationWarning,
                stacklevel=4,
            )

        super().__init__()
        self.bot = bot
        self.chat_id = chat_id
        self.message_ids = message_ids
        self.from_time = from_time
        self.to_time = to_time
        self.count = count
        self.before = before
        self.after = after

    async def fetch(self) -> Messages:
        """
        Выполняет GET-запрос для получения сообщений с учётом
        параметров фильтрации.

        Преобразует datetime в UNIX timestamp в миллисекундах
        при необходимости.

        Returns:
            Messages: Объект с полученными сообщениями.
        """

        bot = self._ensure_bot()

        params = bot.params.copy()

        if self.chat_id is not None:
            params["chat_id"] = self.chat_id

        if self.message_ids:
            params["message_ids"] = ",".join(self.message_ids)

        if self.from_time is not None:
            params["from"] = to_ms(self.from_time)

        if self.to_time is not None:
            params["to"] = to_ms(self.to_time)

        if self.after is not None:
            params["after"] = to_ms(self.after)

        if self.before is not None:
            params["before"] = to_ms(self.before)

        if self.count is not None:
            params["count"] = self.count

        response = await super().request(
            method=HTTPMethod.GET,
            path=ApiPath.MESSAGES,
            model=Messages,
            params=params,
        )

        return cast(Messages, response)
