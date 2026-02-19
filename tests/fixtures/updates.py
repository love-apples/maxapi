"""Фикстуры для отдельных типов обновлений.

Каждая фикстура возвращает экземпляр соответствующей pydantic-модели обновления
с минимальным набором полей, пригодным для тестирования.

Нейминг: fixture_<update_type_name>
Пример: fixture_message_created
"""

import pytest
from maxapi.enums.chat_status import ChatStatus
from maxapi.enums.chat_type import ChatType
from maxapi.enums.update import UpdateType
from maxapi.types.callback import Callback
from maxapi.types.chats import Chat
from maxapi.types.message import Message, MessageBody, Recipient
from maxapi.types.updates.bot_added import BotAdded
from maxapi.types.updates.bot_removed import BotRemoved
from maxapi.types.updates.bot_started import BotStarted
from maxapi.types.updates.bot_stopped import BotStopped
from maxapi.types.updates.chat_title_changed import ChatTitleChanged
from maxapi.types.updates.dialog_cleared import DialogCleared
from maxapi.types.updates.dialog_muted import DialogMuted
from maxapi.types.updates.dialog_removed import DialogRemoved
from maxapi.types.updates.dialog_unmuted import DialogUnmuted
from maxapi.types.updates.message_callback import MessageCallback
from maxapi.types.updates.message_chat_created import MessageChatCreated
from maxapi.types.updates.message_created import MessageCreated
from maxapi.types.updates.message_edited import MessageEdited
from maxapi.types.updates.message_removed import MessageRemoved
from maxapi.types.updates.user_added import UserAdded
from maxapi.types.updates.user_removed import UserRemoved
from maxapi.types.users import User


# Nested object fixtures — use faker for simple params
@pytest.fixture
def user_obj(faker) -> User:
    return User(
        user_id=faker.random_int(min=1, max=99999),
        first_name=faker.first_name(),
        last_name=faker.last_name(),
        is_bot=False,
        last_activity_time=int(faker.date_time().timestamp()),
    )


@pytest.fixture
def bot_user_obj(faker) -> User:
    return User(
        user_id=faker.random_int(min=100000, max=199999),
        first_name=faker.first_name(),
        last_name=None,
        is_bot=True,
        last_activity_time=int(faker.date_time().timestamp()),
    )


@pytest.fixture
def message_body(faker) -> MessageBody:
    return MessageBody(mid=faker.uuid4(), seq=1, text=faker.sentence())


@pytest.fixture
def recipient(faker) -> Recipient:
    return Recipient(
        chat_id=faker.random_int(min=1, max=99999), chat_type=ChatType.DIALOG
    )


@pytest.fixture
def message_obj(user_obj, recipient, message_body, faker) -> Message:
    return Message(
        sender=user_obj,
        recipient=recipient,
        timestamp=int(faker.date_time().timestamp()),
        body=message_body,
    )


@pytest.fixture
def chat_obj(faker) -> Chat:
    return Chat(
        chat_id=faker.random_int(min=1, max=99999),
        type=ChatType.CHAT,
        status=ChatStatus.ACTIVE,
        last_event_time=int(faker.date_time().timestamp()),
        participants_count=1,
        is_public=False,
    )


@pytest.fixture
def callback_obj(faker, user_obj) -> Callback:
    return Callback(
        timestamp=int(faker.date_time().timestamp()),
        callback_id=faker.uuid4(),
        user=user_obj,
    )


# Per-update fixtures that reuse nested fixtures
@pytest.fixture
def fixture_message_created(message_obj, faker) -> MessageCreated:
    return MessageCreated(
        update_type=UpdateType.MESSAGE_CREATED,
        timestamp=int(faker.date_time().timestamp()),
        message=message_obj,
    )


@pytest.fixture
def fixture_message_edited(message_obj, faker) -> MessageEdited:
    return MessageEdited(
        update_type=UpdateType.MESSAGE_EDITED,
        timestamp=int(faker.date_time().timestamp()),
        message=message_obj,
    )


@pytest.fixture
def fixture_message_removed(faker) -> MessageRemoved:
    return MessageRemoved(
        update_type=UpdateType.MESSAGE_REMOVED,
        timestamp=int(faker.date_time().timestamp()),
        message_id=faker.uuid4(),
        chat_id=faker.random_int(min=1, max=99999),
        user_id=faker.random_int(min=1, max=99999),
    )


@pytest.fixture
def fixture_message_callback(
    message_obj, callback_obj, faker
) -> MessageCallback:
    return MessageCallback(
        update_type=UpdateType.MESSAGE_CALLBACK,
        timestamp=int(faker.date_time().timestamp()),
        message=message_obj,
        callback=callback_obj,
    )


@pytest.fixture
def fixture_message_chat_created(chat_obj, faker) -> MessageChatCreated:
    return MessageChatCreated(
        update_type=UpdateType.MESSAGE_CHAT_CREATED,
        timestamp=int(faker.date_time().timestamp()),
        chat=chat_obj,
        title=faker.sentence(),
    )


@pytest.fixture
def fixture_bot_added(bot_user_obj, faker) -> BotAdded:
    return BotAdded(
        update_type=UpdateType.BOT_ADDED,
        timestamp=int(faker.date_time().timestamp()),
        chat_id=faker.random_int(min=1, max=99999),
        user=bot_user_obj,
        is_channel=False,
    )


@pytest.fixture
def fixture_bot_removed(bot_user_obj, faker) -> BotRemoved:
    return BotRemoved(
        update_type=UpdateType.BOT_REMOVED,
        timestamp=int(faker.date_time().timestamp()),
        chat_id=faker.random_int(min=1, max=99999),
        user=bot_user_obj,
        is_channel=False,
    )


@pytest.fixture
def fixture_bot_started(bot_user_obj, faker) -> BotStarted:
    return BotStarted(
        update_type=UpdateType.BOT_STARTED,
        timestamp=int(faker.date_time().timestamp()),
        chat_id=faker.random_int(min=1, max=99999),
        user=bot_user_obj,
    )


@pytest.fixture
def fixture_bot_stopped(bot_user_obj, faker) -> BotStopped:
    return BotStopped(
        update_type=UpdateType.BOT_STOPPED,
        timestamp=int(faker.date_time().timestamp()),
        chat_id=faker.random_int(min=1, max=99999),
        user=bot_user_obj,
    )


@pytest.fixture
def fixture_user_added(user_obj, faker) -> UserAdded:
    return UserAdded(
        update_type=UpdateType.USER_ADDED,
        timestamp=int(faker.date_time().timestamp()),
        chat_id=faker.random_int(min=1, max=99999),
        user=user_obj,
        is_channel=False,
    )


@pytest.fixture
def fixture_user_removed(user_obj, faker) -> UserRemoved:
    return UserRemoved(
        update_type=UpdateType.USER_REMOVED,
        timestamp=int(faker.date_time().timestamp()),
        chat_id=faker.random_int(min=1, max=99999),
        user=user_obj,
        is_channel=False,
    )


@pytest.fixture
def fixture_dialog_cleared(user_obj, faker) -> DialogCleared:
    return DialogCleared(
        update_type=UpdateType.DIALOG_CLEARED,
        timestamp=int(faker.date_time().timestamp()),
        chat_id=faker.random_int(min=1, max=99999),
        user=user_obj,
    )


@pytest.fixture
def fixture_dialog_muted(user_obj, faker) -> DialogMuted:
    return DialogMuted(
        update_type=UpdateType.DIALOG_MUTED,
        timestamp=int(faker.date_time().timestamp()),
        chat_id=faker.random_int(min=1, max=99999),
        muted_until=9999999999,
        user=user_obj,
    )


@pytest.fixture
def fixture_dialog_unmuted(user_obj, faker) -> DialogUnmuted:
    return DialogUnmuted(
        update_type=UpdateType.DIALOG_UNMUTED,
        timestamp=int(faker.date_time().timestamp()),
        chat_id=faker.random_int(min=1, max=99999),
        user=user_obj,
    )


@pytest.fixture
def fixture_dialog_removed(user_obj, faker) -> DialogRemoved:
    return DialogRemoved(
        update_type=UpdateType.DIALOG_REMOVED,
        timestamp=int(faker.date_time().timestamp()),
        chat_id=faker.random_int(min=1, max=99999),
        user=user_obj,
    )


@pytest.fixture
def fixture_chat_title_changed(user_obj, faker) -> ChatTitleChanged:
    return ChatTitleChanged(
        update_type=UpdateType.CHAT_TITLE_CHANGED,
        timestamp=int(faker.date_time().timestamp()),
        chat_id=faker.random_int(min=1, max=99999),
        user=user_obj,
        title=faker.sentence(),
    )
