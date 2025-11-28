from typing import Union

from ...types.updates.bot_added import BotAdded
from ...types.updates.bot_removed import BotRemoved
from ...types.updates.bot_started import BotStarted
from ...types.updates.chat_title_changed import ChatTitleChanged
from ...types.updates.message_callback import MessageCallback
from ...types.updates.message_chat_created import MessageChatCreated
from ...types.updates.message_created import MessageCreated
from ...types.updates.message_edited import MessageEdited
from ...types.updates.message_removed import MessageRemoved
from ...types.updates.user_added import UserAdded
from ...types.updates.user_removed import UserRemoved

UpdateUnion = Union[
    BotAdded,
    BotRemoved,
    BotStarted,
    ChatTitleChanged,
    MessageCallback,
    MessageChatCreated,
    MessageCreated,
    MessageEdited,
    MessageRemoved,
    UserAdded,
    UserRemoved,
]
