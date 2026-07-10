import warnings
from typing import TYPE_CHECKING, Any, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..types.users import ChatAdmin
from .types.added_admin_chat import AddedListAdminChat

if TYPE_CHECKING:
    from ..bot import Bot


class AddAdminChat(BaseConnection):
    """
    Класс для назначения администраторов чата или канала через API.

    https://dev.max.ru/docs-api/methods/POST/chats/-chatId-/members/admins

    Attributes:
        bot: Экземпляр бота, через который выполняется запрос.
        chat_id: Идентификатор чата или канала.
        admins: Список администраторов для назначения.
        marker: Устаревший параметр, больше не отправляется в API.
    """

    def __init__(
        self,
        bot: "Bot",
        chat_id: int,
        admins: list[ChatAdmin],
        marker: int | None = None,
    ):
        if marker is not None:
            warnings.warn(
                "Параметр marker в AddAdminChat устарел и "
                "игнорируется: POST /chats/{chatId}/members/admins "
                "больше не поддерживает marker.",
                DeprecationWarning,
                stacklevel=2,
            )

        super().__init__()
        self.bot = bot
        self.chat_id = chat_id
        self.admins = admins
        self.marker = marker

    async def fetch(self) -> AddedListAdminChat:
        """
        Выполняет HTTP POST запрос для назначения администраторов.

        Формирует JSON с данными администраторов и отправляет запрос на
        соответствующий API-эндпоинт.

        Returns:
            AddedListAdminChat: Результат операции с информацией
                об успешности.
        """

        bot = self._ensure_bot()

        json: dict[str, Any] = {}

        json["admins"] = [admin.model_dump() for admin in self.admins]

        response = await super().request(
            method=HTTPMethod.POST,
            path=ApiPath.CHATS.value
            + "/"
            + str(self.chat_id)
            + ApiPath.MEMBERS
            + ApiPath.ADMINS,
            model=AddedListAdminChat,
            params=bot.params,
            json=json,
        )

        return cast(AddedListAdminChat, response)
