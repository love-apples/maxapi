from logging import getLogger
from typing import TYPE_CHECKING, Any, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..exceptions.max import MaxIconParamsException
from ..types.attachments.image import PhotoAttachmentRequestPayload
from ..types.chats import Chat

logger = getLogger(__name__)


if TYPE_CHECKING:
    from ..bot import Bot


class EditChat(BaseConnection):
    """
    Класс для редактирования информации о чате через API.

    https://dev.max.ru/docs-api/methods/PATCH/chats/-chatId-

    Attributes:
        bot: Экземпляр бота для выполнения запроса.
        chat_id: Идентификатор чата для редактирования.
        icon: Новый значок
            (иконка) чата.
        title: Новое название чата.
        pin: Идентификатор закреплённого сообщения.
        notify: Включение или отключение уведомлений
            (по умолчанию True).
    """

    def __init__(
        self,
        bot: "Bot",
        chat_id: int,
        icon: PhotoAttachmentRequestPayload | None = None,
        title: str | None = None,
        pin: str | None = None,
        *,
        notify: bool | None = None,
    ):
        if title is not None and not (1 <= len(title) <= 200):
            raise ValueError(
                "title не должен быть меньше 1 или больше 200 символов"
            )

        super().__init__()
        self.bot = bot
        self.chat_id = chat_id
        self.icon = icon
        self.title = title
        self.pin = pin
        self.notify = notify

    async def fetch(self) -> Chat:
        """
        Выполняет PATCH-запрос для обновления параметров чата.

        Валидация:
            - Проверяется, что в `icon` атрибуты модели
                взаимоисключающие (в модели должно быть ровно 2 поля
                с None).
            - Если условие не выполнено, логируется ошибка и запрос
                не отправляется.

        Returns:
            Chat: Обновлённый объект чата.
        """

        bot = self._ensure_bot()

        json: dict[str, Any] = {}

        if self.icon:
            dump = self.icon.model_dump()

            if sum(value is not None for value in dump.values()) != 1:
                raise MaxIconParamsException(
                    "Все атрибуты модели Icon являются взаимоисключающими | "
                    "https://dev.max.ru/docs-api/methods/PATCH/chats/-chatId-"
                )

            json["icon"] = dump

        if self.title:
            json["title"] = self.title
        if self.pin:
            json["pin"] = self.pin
        if self.notify is not None:
            json["notify"] = self.notify

        response = await super().request(
            method=HTTPMethod.PATCH,
            path=ApiPath.CHATS.value + "/" + str(self.chat_id),
            model=Chat,
            params=bot.params,
            json=json,
        )

        return cast(Chat, response)
