import warnings
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from ..connection.base import BaseConnection
from ..enums.api_path import ApiPath
from ..enums.http_method import HTTPMethod
from ..types.attachments.image import PhotoAttachmentRequestPayload
from ..types.command import BotCommand
from ..types.users import User

if TYPE_CHECKING:
    from ..bot import Bot


class ChangeInfo(BaseConnection):
    """
    Класс для изменения данных текущего бота.

    .. deprecated:: 0.9.8
        Этот метод отсутствует в официальной swagger-спецификации API MAX.
        Использование не рекомендуется.

    https://dev.max.ru/docs-api/methods/PATCH/me

    Args:
        first_name (str, optional): Имя бота (1–64 символа).
        last_name (str, optional): Второе имя бота (1–64 символа).
        description (str, optional): Описание бота (1–16000 символов).
        commands (list[BotCommand], optional): Список команд (до 32 элементов).
        photo (PhotoAttachmentRequestPayload, optional): Фото бота.

    Note:
        Метод :meth:`fetch` возвращает объект :class:`User` с обновленными данными бота.
    """

    def __init__(
        self,
        bot: "Bot",
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        description: Optional[str] = None,
        commands: Optional[List[BotCommand]] = None,
        photo: Optional[PhotoAttachmentRequestPayload] = None,
    ):
        warnings.warn(
            "ChangeInfo устарел и отсутствует в официальной swagger-спецификации API MAX. "
            "Использование не рекомендуется.",
            DeprecationWarning,
            stacklevel=2,
        )

        if not any([first_name, last_name, description, commands, photo]):
            raise ValueError(
                "Нужно указать хотя бы один параметр для изменения"
            )

        if first_name is not None and not (1 <= len(first_name) <= 64):
            raise ValueError("first_name должен быть от 1 до 64 символов")

        if last_name is not None and not (1 <= len(last_name) <= 64):
            raise ValueError("last_name должен быть от 1 до 64 символов")

        if description is not None and not (1 <= len(description) <= 16000):
            raise ValueError("description должен быть от 1 до 16000 символов")

        if commands is not None and len(commands) > 32:
            raise ValueError("commands не может содержать больше 32 элементов")

        self.bot = bot
        self.first_name = first_name
        self.last_name = last_name
        self.description = description
        self.commands = commands
        self.photo = photo

    async def fetch(self) -> User:
        """
        Отправляет запрос на изменение информации о боте.

        Returns:
            User: Объект с обновленными данными бота
        """

        bot = self._ensure_bot()

        json: Dict[str, Any] = {}

        if self.first_name:
            json["first_name"] = self.first_name
        if self.last_name:
            json["last_name"] = self.last_name
        if self.description:
            json["description"] = self.description
        if self.commands:
            json["commands"] = [
                command.model_dump() for command in self.commands
            ]
        if self.photo:
            json["photo"] = self.photo.model_dump()

        response = await super().request(
            method=HTTPMethod.PATCH,
            path=ApiPath.ME,
            model=User,
            params=bot.params,
            json=json,
        )

        return cast(User, response)
