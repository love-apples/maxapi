from typing import Literal

from ...enums.chat_permission import ChatPermission
from ...enums.update import UpdateType
from .base_update import BaseUpdate


class BotAdminPermissionsChanged(BaseUpdate):
    """
    Обновление об изменении прав бота-администратора в чате или канале.

    Приходит, когда боту выдали или отозвали права администратора
    либо изменили их набор.

    Note:
        По данным MAX API событие доступно только через Webhook:
        подпишитесь на него в bot.subscribe_webhook(update_types=...).
        Через Long Polling оно пока не приходит.

    Attributes:
        chat_id: Идентификатор чата или канала, где изменились права.
        user_id: Идентификатор пользователя или бота, изменившего права.
        bot_id: Идентификатор бота, чьи права изменились.
        is_channel: Произошло ли изменение в канале.
        is_admin: Является ли бот администратором после изменения.
        permissions: Актуальный набор прав бота. Может быть None.
    """

    chat_id: int
    user_id: int
    bot_id: int
    is_channel: bool
    is_admin: bool
    permissions: list[ChatPermission] | None = None
    update_type: Literal[UpdateType.BOT_ADMIN_PERMISSIONS_CHANGED] = (
        UpdateType.BOT_ADMIN_PERMISSIONS_CHANGED
    )

    def get_ids(self) -> tuple[int | None, int | None]:
        """
        Возвращает кортеж идентификаторов (chat_id, user_id).

        Returns:
            Tuple[Optional[int], Optional[int]]: Идентификаторы чата и
                пользователя, изменившего права.
        """

        return self.chat_id, self.user_id
