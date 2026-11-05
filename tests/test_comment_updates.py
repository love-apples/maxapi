"""Тесты событий комментариев: comment_created/edited/removed.

Покрывает:
  - парсинг сырых payload из OpenAPI-схемы через UpdateUnionAdapter;
  - обогащение событий (chat, from_user, bot) с auto_requests и без;
  - шорткаты CommentMessage.reply/delete из входящего события;
  - диспетчеризацию через @dp.comment_*.
"""

from asyncio.exceptions import TimeoutError as AsyncioTimeoutError
from unittest.mock import AsyncMock, MagicMock

import pytest
from maxapi import F
from maxapi.enums.chat_type import ChatType
from maxapi.enums.message_link_type import MessageLinkType
from maxapi.enums.update import UpdateType
from maxapi.exceptions.max import MaxApiError, MaxConnection
from maxapi.types.fetchable import ChatRef, FromUserRef
from maxapi.types.updates import UpdateUnionAdapter
from maxapi.types.updates.comment_created import CommentCreated
from maxapi.types.updates.comment_edited import CommentEdited
from maxapi.types.updates.comment_removed import CommentRemoved
from maxapi.utils.updates import enrich_event

from tests.conftest import setup_dispatcher_for_handle

CHANNEL_ID = -70001
POST_ID = "mid.post.1"
COMMENT_ID = "mid.comment.1"


def _comment_payload(update_type: str, *, sender: bool = True) -> dict:
    message: dict = {
        "recipient": {
            "chat_id": CHANNEL_ID,
            "chat_type": "channel",
            "post_id": POST_ID,
        },
        "timestamp": 1_700_000_000_000,
        "body": {"mid": COMMENT_ID, "seq": 3, "text": "привет"},
    }
    if sender:
        message["sender"] = {
            "user_id": 42,
            "first_name": "Ann",
            "is_bot": False,
            "last_activity_time": 1_700_000_000_000,
        }
    return {
        "update_type": update_type,
        "timestamp": 1_700_000_000_001,
        "message": message,
        "user_locale": "ru",
    }


# ===========================================================================
# Парсинг
# ===========================================================================


class TestParsing:
    """Сырые payload из схемы парсятся в нужные модели."""

    @pytest.mark.parametrize(
        ("update_type", "model"),
        [
            ("comment_created", CommentCreated),
            ("comment_edited", CommentEdited),
        ],
    )
    def test_comment_with_message(self, update_type, model):
        event = UpdateUnionAdapter.validate_python(
            _comment_payload(update_type)
        )

        assert isinstance(event, model)
        assert event.message.body.mid == COMMENT_ID
        assert event.message.post_message_id == POST_ID
        assert event.get_ids() == (CHANNEL_ID, 42)

    def test_comment_from_channel_without_sender(self):
        event = UpdateUnionAdapter.validate_python(
            _comment_payload("comment_created", sender=False)
        )

        assert isinstance(event, CommentCreated)
        assert event.message.sender is None
        assert event.get_ids() == (CHANNEL_ID, None)

    def test_comment_removed(self):
        event = UpdateUnionAdapter.validate_python(
            {
                "update_type": "comment_removed",
                "timestamp": 1,
                "message_id": COMMENT_ID,
                "chat_id": CHANNEL_ID,
                "user_id": 42,
                "post_id": POST_ID,
            }
        )

        assert isinstance(event, CommentRemoved)
        assert event.update_type == UpdateType.COMMENT_REMOVED
        assert event.post_id == POST_ID
        assert event.get_ids() == (CHANNEL_ID, 42)


# ===========================================================================
# Обогащение
# ===========================================================================


class TestEnrich:
    """enrich_event для событий комментариев."""

    @pytest.mark.parametrize(
        "fixture_name", ["fixture_comment_created", "fixture_comment_edited"]
    )
    async def test_chat_and_from_user_from_message(
        self, request, bot, fixture_name
    ):
        event = request.getfixturevalue(fixture_name)
        fake_chat = MagicMock()
        bot.get_chat_by_id = AsyncMock(return_value=fake_chat)
        bot.get_chat_member = AsyncMock()

        result = await enrich_event(event, bot)

        bot.get_chat_by_id.assert_awaited_once_with(
            event.message.recipient.chat_id
        )
        bot.get_chat_member.assert_not_called()
        assert result.chat is fake_chat
        assert result.from_user is event.message.sender
        assert result.message.bot is bot

    async def test_sender_none_keeps_from_user_none(
        self, bot, fixture_comment_created
    ):
        fixture_comment_created.message.sender = None
        bot.get_chat_by_id = AsyncMock(return_value=MagicMock())
        bot.get_chat_member = AsyncMock()

        result = await enrich_event(fixture_comment_created, bot)

        bot.get_chat_member.assert_not_called()
        assert result.from_user is None

    async def test_removed_fetches_chat_member(
        self, bot, fixture_comment_removed
    ):
        member = MagicMock()
        bot.get_chat_by_id = AsyncMock(return_value=MagicMock())
        bot.get_chat_member = AsyncMock(return_value=member)

        result = await enrich_event(fixture_comment_removed, bot)

        bot.get_chat_by_id.assert_awaited_once_with(
            fixture_comment_removed.chat_id
        )
        bot.get_chat_member.assert_awaited_once_with(
            chat_id=fixture_comment_removed.chat_id,
            user_id=fixture_comment_removed.user_id,
        )
        assert result.from_user is member

    async def test_removed_member_error_is_logged(
        self, bot, fixture_comment_removed, caplog
    ):
        bot.get_chat_by_id = AsyncMock(return_value=MagicMock())
        bot.get_chat_member = AsyncMock(
            side_effect=MaxApiError(code=404, raw={"message": "not found"})
        )

        result = await enrich_event(fixture_comment_removed, bot)

        assert result.from_user is None
        assert "Не удалось получить участника" in caplog.text

    @pytest.mark.parametrize(
        "fixture_name",
        ["fixture_comment_removed", "fixture_bot_admin_permissions_changed"],
    )
    @pytest.mark.parametrize(
        "error",
        [MaxConnection("connection lost"), AsyncioTimeoutError()],
        ids=["max_connection", "timeout"],
    )
    async def test_member_network_error_is_logged(
        self, request, bot, fixture_name, error, caplog
    ):
        """Сетевая ошибка get_chat_member не всплывает и пишется в лог."""
        event = request.getfixturevalue(fixture_name)
        bot.get_chat_by_id = AsyncMock(return_value=MagicMock())
        bot.get_chat_member = AsyncMock(side_effect=error)

        result = await enrich_event(event, bot)

        assert result.from_user is None
        assert "get_chat_member" in caplog.text

    async def test_auto_requests_false_builds_lazy_refs(
        self, bot, fixture_comment_created, fixture_comment_removed
    ):
        bot.auto_requests = False
        bot.get_chat_by_id = AsyncMock()
        bot.get_chat_member = AsyncMock()

        created = await enrich_event(fixture_comment_created, bot)
        removed = await enrich_event(fixture_comment_removed, bot)

        bot.get_chat_by_id.assert_not_called()
        bot.get_chat_member.assert_not_called()
        assert isinstance(created.chat, ChatRef)
        assert created.from_user is fixture_comment_created.message.sender
        assert isinstance(removed.chat, ChatRef)
        assert isinstance(removed.from_user, FromUserRef)

        member = MagicMock()
        bot.get_chat_member = AsyncMock(return_value=member)
        assert await removed.fetch_from_user() is member
        bot.get_chat_member.assert_awaited_once_with(
            chat_id=fixture_comment_removed.chat_id,
            user_id=fixture_comment_removed.user_id,
        )


# ===========================================================================
# Шорткаты комментария из события
# ===========================================================================


class TestShortcuts:
    """CommentMessage из события работает без ручного post_message_id."""

    async def test_reply_uses_post_id(self, bot, fixture_comment_created):
        bot.auto_requests = False
        bot.send_comment = AsyncMock()
        event = await enrich_event(fixture_comment_created, bot)

        await event.message.reply("ответ")

        kwargs = bot.send_comment.await_args.kwargs
        assert kwargs["message_id"] == event.message.recipient.post_id
        assert kwargs["text"] == "ответ"
        assert kwargs["link"].type == MessageLinkType.REPLY
        assert kwargs["link"].mid == event.message.body.mid

    async def test_delete_uses_post_and_comment_ids(
        self, bot, fixture_comment_edited
    ):
        bot.auto_requests = False
        bot.delete_comment = AsyncMock()
        event = await enrich_event(fixture_comment_edited, bot)

        await event.message.delete()

        bot.delete_comment.assert_awaited_once_with(
            message_id=event.message.recipient.post_id,
            comment_id=event.message.body.mid,
        )


# ===========================================================================
# Диспетчеризация
# ===========================================================================


class TestDispatch:
    """Хендлеры @dp.comment_* получают свои события."""

    @pytest.mark.parametrize(
        ("event_name", "fixture_name"),
        [
            ("comment_created", "fixture_comment_created"),
            ("comment_edited", "fixture_comment_edited"),
            ("comment_removed", "fixture_comment_removed"),
        ],
    )
    async def test_handler_called(
        self, request, dispatcher, bot, event_name, fixture_name
    ):
        event = request.getfixturevalue(fixture_name)
        handled = []

        @getattr(dispatcher, event_name)()
        async def _handler(event):
            handled.append(event)

        @dispatcher.message_created()
        async def _other(event):  # pragma: no cover
            handled.append("wrong")

        setup_dispatcher_for_handle(dispatcher, bot)
        await dispatcher.handle(event)

        assert handled == [event]

    async def test_magic_filter_on_comment_text(
        self, dispatcher, bot, fixture_comment_created
    ):
        fixture_comment_created.message.body.text = "http://spam"
        handled = []

        @dispatcher.comment_created(F.message.body.text.contains("http"))
        async def _handler(event):
            handled.append(event)

        setup_dispatcher_for_handle(dispatcher, bot)
        await dispatcher.handle(fixture_comment_created)

        assert handled == [fixture_comment_created]


def test_channel_chat_type_in_fixture(fixture_comment_created):
    assert (
        fixture_comment_created.message.recipient.chat_type == ChatType.CHANNEL
    )
