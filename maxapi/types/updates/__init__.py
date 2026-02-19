from typing import Annotated

from pydantic import Field, TypeAdapter

from ...types.updates.bot_added import BotAdded
from ...types.updates.bot_removed import BotRemoved
from ...types.updates.bot_started import BotStarted
from ...types.updates.bot_stopped import BotStopped
from ...types.updates.chat_title_changed import ChatTitleChanged
from ...types.updates.dialog_cleared import DialogCleared
from ...types.updates.dialog_muted import DialogMuted
from ...types.updates.dialog_unmuted import DialogUnmuted
from ...types.updates.message_callback import MessageCallback
from ...types.updates.message_chat_created import MessageChatCreated
from ...types.updates.message_created import MessageCreated
from ...types.updates.message_edited import MessageEdited
from ...types.updates.message_removed import MessageRemoved
from ...types.updates.user_added import UserAdded
from ...types.updates.user_removed import UserRemoved
from .dialog_removed import DialogRemoved

UNKNOWN_UPDATE_DISCLAIMER = (
    "Получен неизвестный тип обновления через вебхук: {update_type}"
    "Убедитесь, что используете актуальную версию maxapi. "
    "Если проблема сохраняется, создайте issue в репозитории проекта: "
    "https://github.com/love-apples/maxapi/issues"
)

UpdateUnion = Annotated[
    BotAdded
    | BotRemoved
    | BotStarted
    | BotStopped
    | ChatTitleChanged
    | DialogCleared
    | DialogMuted
    | DialogRemoved
    | DialogUnmuted
    | MessageCallback
    | MessageChatCreated
    | MessageCreated
    | MessageEdited
    | MessageRemoved
    | UserAdded
    | UserRemoved,
    Field(discriminator="update_type"),
]

UpdateUnionAdapter: TypeAdapter = TypeAdapter(UpdateUnion)
