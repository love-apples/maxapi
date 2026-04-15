import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from maxapi.enums.chat_status import ChatStatus
from maxapi.enums.chat_type import ChatType
from maxapi.enums.message_link_type import MessageLinkType
from maxapi.enums.update import UpdateType
from maxapi.methods.types.getted_list_admin_chat import GettedListAdminChat
from maxapi.methods.types.getted_members_chat import GettedMembersChat
from maxapi.types.callback import Callback
from maxapi.types.chats import Chat, ChatMember
from maxapi.types.message import Message, MessageBody, Recipient
from maxapi.types.updates.bot_started import BotStarted
from maxapi.types.updates.message_callback import MessageCallback
from maxapi.types.users import ChatAdmin, User


class ShortcutBot:
    def __init__(self):
        self.send_message = AsyncMock(return_value={"kind": "send"})
        self.send_action = AsyncMock(return_value={"kind": "action"})
        self.edit_chat = AsyncMock(return_value={"kind": "edit_chat"})
        self.get_pin_message = AsyncMock(
            return_value=SimpleNamespace(message="pinned")
        )
        self.pin_message = AsyncMock(return_value={"kind": "pin"})
        self.delete_pin_message = AsyncMock(return_value={"kind": "unpin"})
        self.get_messages = AsyncMock(return_value={"kind": "history"})
        self.delete_me_from_chat = AsyncMock(return_value={"kind": "leave"})
        self.delete_chat = AsyncMock(return_value={"kind": "delete"})
        self.get_chat_members = AsyncMock(return_value={"kind": "members"})
        self.get_chat_member = AsyncMock(return_value={"kind": "member"})
        self.add_chat_members = AsyncMock(
            return_value={"kind": "add_members"}
        )
        self.kick_chat_member = AsyncMock(return_value={"kind": "kick"})
        self.get_me_from_chat = AsyncMock(return_value={"kind": "me"})
        self.get_list_admin_chat = AsyncMock(
            return_value={"kind": "admins"}
        )
        self.add_list_admin_chat = AsyncMock(
            return_value={"kind": "add_admins"}
        )
        self.remove_admin = AsyncMock(return_value={"kind": "remove_admin"})
        self.send_callback = AsyncMock(return_value={"kind": "callback"})
        self.delete_message = AsyncMock(
            return_value={"kind": "delete_message"}
        )
        self.resolve_format = Mock(
            side_effect=lambda format, parse_mode=None: (
                format if format is not None else parse_mode
            )
        )


def _make_user(user_id: int = 1) -> User:
    return User(
        user_id=user_id,
        first_name="Alice",
        is_bot=False,
        last_activity_time=1,
    )


def _make_message(chat_id: int = 100, user_id: int | None = None) -> Message:
    return Message(
        sender=_make_user(2),
        recipient=Recipient(
            chat_id=chat_id,
            user_id=user_id,
            chat_type=ChatType.CHAT,
        ),
        timestamp=1,
        body=MessageBody(mid="mid-1", seq=1, text="hello"),
    )


def _make_member(user_id: int) -> ChatMember:
    return ChatMember(
        user_id=user_id,
        first_name=f"User {user_id}",
        is_bot=False,
        last_activity_time=1,
    )


async def test_user_send_uses_bound_user_id():
    bot = ShortcutBot()
    user = _make_user(77)
    user.bot = bot

    await user.send("hello")

    bot.send_message.assert_awaited_once_with(
        chat_id=None,
        user_id=77,
        text="hello",
        attachments=None,
        link=None,
        notify=None,
        format=None,
        parse_mode=None,
        disable_link_preview=None,
        sleep_after_input_media=True,
    )


async def test_chat_high_level_shortcuts_delegate_to_bot():
    bot = ShortcutBot()
    chat = Chat(
        chat_id=100,
        type=ChatType.CHAT,
        status=ChatStatus.ACTIVE,
        last_event_time=1,
        participants_count=1,
        is_public=False,
    )
    chat.bot = bot
    message = _make_message(chat_id=100)

    await chat.send("hi")
    await chat.action()
    await chat.rename("New title")
    pinned = await chat.fetch_pinned_message()
    await chat.pin(message)
    await chat.unpin()
    await chat.history(count=10)
    await chat.leave()
    await chat.delete()
    await chat.members.list(count=5)
    await chat.members.get(5)
    await chat.members.add([5, 6])
    await chat.members.kick(7, block=True)
    await chat.members.me()
    await chat.admins.list()
    await chat.admins.add([ChatAdmin(user_id=9, permissions=[])])
    await chat.admins.remove(9)

    assert pinned == "pinned"
    bot.send_message.assert_awaited_once_with(
        chat_id=100,
        user_id=None,
        text="hi",
        attachments=None,
        link=None,
        notify=None,
        format=None,
        parse_mode=None,
        disable_link_preview=None,
        sleep_after_input_media=True,
    )
    bot.send_action.assert_awaited_once()
    bot.edit_chat.assert_awaited_once_with(
        chat_id=100,
        icon=None,
        title="New title",
        pin=None,
        notify=None,
    )
    bot.pin_message.assert_awaited_once_with(
        chat_id=100,
        message_id="mid-1",
        notify=None,
    )
    bot.delete_pin_message.assert_awaited_once_with(100)
    bot.get_messages.assert_awaited_once_with(
        chat_id=100,
        message_ids=None,
        from_time=None,
        to_time=None,
        count=10,
    )
    bot.delete_me_from_chat.assert_awaited_once_with(100)
    bot.delete_chat.assert_awaited_once_with(100)
    bot.get_chat_members.assert_awaited_once_with(
        chat_id=100,
        user_ids=None,
        marker=None,
        count=5,
    )
    bot.get_chat_member.assert_awaited_once_with(chat_id=100, user_id=5)
    bot.add_chat_members.assert_awaited_once_with(
        chat_id=100,
        user_ids=[5, 6],
    )
    bot.kick_chat_member.assert_awaited_once_with(
        chat_id=100,
        user_id=7,
        block=True,
    )
    bot.get_me_from_chat.assert_awaited_once_with(100)
    bot.get_list_admin_chat.assert_awaited_once_with(100, marker=None)
    admin_call = bot.add_list_admin_chat.await_args.kwargs
    assert admin_call["chat_id"] == 100
    assert admin_call["marker"] is None
    assert len(admin_call["admins"]) == 1
    assert admin_call["admins"][0].user_id == 9
    bot.remove_admin.assert_awaited_once_with(chat_id=100, user_id=9)


async def test_chat_typing_context_sends_periodic_actions():
    bot = ShortcutBot()
    chat = Chat(
        chat_id=100,
        type=ChatType.CHAT,
        status=ChatStatus.ACTIVE,
        last_event_time=1,
        participants_count=1,
        is_public=False,
    )
    chat.bot = bot

    async with chat.typing(interval=0.01):
        await asyncio.sleep(0.03)

    assert bot.send_action.await_count >= 2


async def test_base_update_shortcuts_use_get_ids():
    bot = ShortcutBot()
    event = BotStarted(
        update_type=UpdateType.BOT_STARTED,
        timestamp=1,
        chat_id=100,
        user=_make_user(44),
    )
    event.bot = bot

    await event.send("hello")
    await event.action()
    await event.mark_seen()

    assert bot.send_message.await_args.kwargs["chat_id"] == 100
    assert bot.send_message.await_args.kwargs["user_id"] == 44
    assert bot.send_action.await_count == 2


async def test_message_send_reply_and_unpin_delegate_to_bot():
    bot = ShortcutBot()
    message = _make_message(chat_id=100)
    message.bot = bot

    await message.send("plain")
    await message.reply("reply")
    await message.unpin()

    first_call = bot.send_message.await_args_list[0].kwargs
    second_call = bot.send_message.await_args_list[1].kwargs

    assert first_call["text"] == "plain"
    assert first_call["link"] is None
    assert second_call["link"].type == MessageLinkType.REPLY
    assert second_call["link"].mid == "mid-1"
    bot.delete_pin_message.assert_awaited_once_with(chat_id=100)


async def test_message_callback_shortcuts_and_legacy_answer():
    bot = ShortcutBot()
    message = _make_message(chat_id=100)
    message.bot = bot

    callback = MessageCallback(
        message=message,
        user_locale=None,
        callback=Callback(
            timestamp=1,
            callback_id="cb-1",
            payload=None,
            user=_make_user(55),
        ),
        update_type=UpdateType.MESSAGE_CALLBACK,
        timestamp=1,
    )
    callback.bot = bot

    await callback.ack("ok")
    ack_kwargs = bot.send_callback.await_args.kwargs
    assert ack_kwargs["callback_id"] == "cb-1"
    assert ack_kwargs["message"] is None
    assert ack_kwargs["notification"] == "ok"

    bot.send_callback.reset_mock()
    await callback.defer("later")
    defer_kwargs = bot.send_callback.await_args.kwargs
    assert defer_kwargs["callback_id"] == "cb-1"
    assert defer_kwargs["message"] is None
    assert defer_kwargs["notification"] == "later"

    bot.send_callback.reset_mock()
    await callback.edit(
        text="updated",
        notification="changed",
        notify=False,
    )
    edit_kwargs = bot.send_callback.await_args.kwargs
    assert edit_kwargs["callback_id"] == "cb-1"
    assert edit_kwargs["message"].text == "updated"
    assert edit_kwargs["message"].attachments == []
    assert edit_kwargs["message"].notify is False
    assert edit_kwargs["notification"] == "changed"

    bot.send_callback.reset_mock()
    await callback.answer(notification="legacy")
    legacy_kwargs = bot.send_callback.await_args.kwargs
    assert legacy_kwargs["message"] is not None
    assert legacy_kwargs["notification"] == "legacy"

    bot.send_message.reset_mock()
    await callback.send("fresh")
    await callback.reply("reply")
    send_kwargs = bot.send_message.await_args_list[0].kwargs
    reply_kwargs = bot.send_message.await_args_list[1].kwargs
    assert send_kwargs["text"] == "fresh"
    assert send_kwargs["link"] is None
    assert reply_kwargs["link"].type == MessageLinkType.REPLY

    await callback.delete()
    await callback.pin(notify=False)
    await callback.unpin()

    bot.delete_message.assert_awaited_once_with(message_id="mid-1")
    bot.pin_message.assert_awaited_once_with(
        chat_id=100,
        message_id="mid-1",
        notify=False,
    )
    bot.delete_pin_message.assert_awaited_once_with(chat_id=100)


async def test_chat_alias_shortcuts_delegate_to_bot():
    bot = ShortcutBot()
    chat = Chat(
        chat_id=100,
        type=ChatType.CHAT,
        status=ChatStatus.ACTIVE,
        last_event_time=1,
        participants_count=1,
        is_public=False,
    )
    chat.bot = bot
    icon = object()

    await chat.set_title("Alias title")
    await chat.set_icon(icon, notify=False)

    title_call = bot.edit_chat.await_args_list[0].kwargs
    icon_call = bot.edit_chat.await_args_list[1].kwargs

    assert title_call == {
        "chat_id": 100,
        "icon": None,
        "title": "Alias title",
        "pin": None,
        "notify": None,
    }
    assert icon_call == {
        "chat_id": 100,
        "icon": icon,
        "title": None,
        "pin": None,
        "notify": False,
    }


async def test_chat_members_pagination_helpers_collect_all_pages():
    bot = ShortcutBot()
    bot.get_chat_members = AsyncMock(
        side_effect=[
            GettedMembersChat(
                members=[_make_member(1), _make_member(2)],
                marker=5,
            ),
            GettedMembersChat(
                members=[_make_member(3)],
                marker=None,
            ),
        ]
    )
    chat = Chat(
        chat_id=100,
        type=ChatType.CHAT,
        status=ChatStatus.ACTIVE,
        last_event_time=1,
        participants_count=1,
        is_public=False,
    )
    chat.bot = bot

    members = [member async for member in chat.members.iter_all(count=2)]

    assert [member.user_id for member in members] == [1, 2, 3]
    assert bot.get_chat_members.await_args_list[0].kwargs == {
        "chat_id": 100,
        "user_ids": None,
        "marker": None,
        "count": 2,
    }
    assert bot.get_chat_members.await_args_list[1].kwargs == {
        "chat_id": 100,
        "user_ids": None,
        "marker": 5,
        "count": 2,
    }

    bot.get_chat_members = AsyncMock(
        side_effect=[
            GettedMembersChat(members=[_make_member(4)], marker=9),
            GettedMembersChat(members=[_make_member(5)], marker=None),
        ]
    )

    members_list = await chat.members.list_all(count=3)

    assert [member.user_id for member in members_list] == [4, 5]
    assert bot.get_chat_members.await_args_list[0].kwargs == {
        "chat_id": 100,
        "user_ids": None,
        "marker": None,
        "count": 3,
    }
    assert bot.get_chat_members.await_args_list[1].kwargs == {
        "chat_id": 100,
        "user_ids": None,
        "marker": 9,
        "count": 3,
    }


async def test_chat_admins_pagination_helpers_collect_all_pages():
    bot = ShortcutBot()
    bot.get_list_admin_chat = AsyncMock(
        side_effect=[
            GettedListAdminChat(
                members=[_make_member(10)],
                marker=7,
            ),
            GettedListAdminChat(
                members=[_make_member(11), _make_member(12)],
                marker=None,
            ),
        ]
    )
    chat = Chat(
        chat_id=100,
        type=ChatType.CHAT,
        status=ChatStatus.ACTIVE,
        last_event_time=1,
        participants_count=1,
        is_public=False,
    )
    chat.bot = bot

    admins = [member async for member in chat.admins.iter_all()]

    assert [member.user_id for member in admins] == [10, 11, 12]
    assert bot.get_list_admin_chat.await_args_list[0].args == (100,)
    assert bot.get_list_admin_chat.await_args_list[0].kwargs == {
        "marker": None,
    }
    assert bot.get_list_admin_chat.await_args_list[1].args == (100,)
    assert bot.get_list_admin_chat.await_args_list[1].kwargs == {
        "marker": 7,
    }

    bot.get_list_admin_chat = AsyncMock(
        side_effect=[
            GettedListAdminChat(members=[_make_member(13)], marker=8),
            GettedListAdminChat(members=[_make_member(14)], marker=None),
        ]
    )

    admins_list = await chat.admins.list_all()

    assert [member.user_id for member in admins_list] == [13, 14]
    assert bot.get_list_admin_chat.await_args_list[0].args == (100,)
    assert bot.get_list_admin_chat.await_args_list[0].kwargs == {
        "marker": None,
    }
    assert bot.get_list_admin_chat.await_args_list[1].args == (100,)
    assert bot.get_list_admin_chat.await_args_list[1].kwargs == {
        "marker": 8,
    }


async def test_pagination_helpers_raise_on_repeated_marker():
    bot = ShortcutBot()
    bot.get_chat_members = AsyncMock(
        side_effect=[
            GettedMembersChat(members=[_make_member(1)], marker=4),
            GettedMembersChat(members=[_make_member(2)], marker=4),
        ]
    )
    chat = Chat(
        chat_id=100,
        type=ChatType.CHAT,
        status=ChatStatus.ACTIVE,
        last_event_time=1,
        participants_count=1,
        is_public=False,
    )
    chat.bot = bot

    with pytest.raises(RuntimeError, match="marker 4"):
        await chat.members.list_all()

    assert bot.get_chat_members.await_count == 2


def test_bind_bot_recursively_sets_bot_on_nested_models():
    from maxapi.utils.runtime import bind_bot

    bot = ShortcutBot()
    sender = _make_user(10)
    message = _make_message(chat_id=100)
    message.sender = sender
    chat = Chat(
        chat_id=100,
        type=ChatType.CHAT,
        status=ChatStatus.ACTIVE,
        last_event_time=1,
        participants_count=1,
        is_public=False,
        dialog_with_user=_make_user(20),
        pinned_message=message,
    )

    bind_bot(chat, bot)

    assert chat.bot is bot
    assert chat.dialog_with_user.bot is bot
    assert chat.pinned_message.bot is bot
    assert chat.pinned_message.sender.bot is bot
