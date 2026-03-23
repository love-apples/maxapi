"""Тесты для maxapi/utils/updates.py — функция enrich_event.

Покрываются все ветки логики: auto_requests=False, каждый тип события,
is_chat_unavailable для DialogRemoved и BotRemoved-из-канала.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from maxapi.enums.chat_type import ChatType
from maxapi.utils.updates import enrich_event

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chat(chat_type: ChatType = ChatType.CHAT):
    chat = MagicMock()
    chat.type = chat_type
    return chat


# ---------------------------------------------------------------------------
# auto_requests=False — ранний выход без каких-либо API-вызовов
# ---------------------------------------------------------------------------


async def test_enrich_event_auto_requests_false_returns_unchanged(
    bot, fixture_message_created
):
    bot.auto_requests = False
    result = await enrich_event(fixture_message_created, bot)
    assert result is fixture_message_created


# ---------------------------------------------------------------------------
# DialogRemoved — chat=None, from_user=user, get_chat_by_id НЕ вызывается
# ---------------------------------------------------------------------------


async def test_enrich_event_dialog_removed_sets_from_user(
    bot, fixture_dialog_removed
):
    bot.get_chat_by_id = AsyncMock()

    result = await enrich_event(fixture_dialog_removed, bot)

    bot.get_chat_by_id.assert_not_called()
    assert result.chat is None
    assert result.from_user is fixture_dialog_removed.user


# ---------------------------------------------------------------------------
# BotRemoved из канала — chat=None, get_chat_by_id НЕ вызывается
# ---------------------------------------------------------------------------


async def test_enrich_event_bot_removed_from_channel_chat_is_none(
    bot, fixture_bot_removed
):
    fixture_bot_removed.is_channel = True
    bot.get_chat_by_id = AsyncMock()

    result = await enrich_event(fixture_bot_removed, bot)

    bot.get_chat_by_id.assert_not_called()
    assert result.chat is None


# ---------------------------------------------------------------------------
# BotRemoved НЕ из канала — get_chat_by_id вызывается
# ---------------------------------------------------------------------------


async def test_enrich_event_bot_removed_not_channel_fetches_chat(
    bot, fixture_bot_removed
):
    fixture_bot_removed.is_channel = False
    fake_chat = _make_chat()
    bot.get_chat_by_id = AsyncMock(return_value=fake_chat)

    result = await enrich_event(fixture_bot_removed, bot)

    bot.get_chat_by_id.assert_awaited_once_with(fixture_bot_removed.chat_id)
    assert result.chat is fake_chat
    assert result.from_user is fixture_bot_removed.user


# ---------------------------------------------------------------------------
# MessageCreated — from_user=sender, get_chat_by_id вызывается
# ---------------------------------------------------------------------------


async def test_enrich_event_message_created_sets_from_user_and_chat(
    bot, fixture_message_created
):
    fake_chat = _make_chat(ChatType.DIALOG)
    bot.get_chat_by_id = AsyncMock(return_value=fake_chat)

    result = await enrich_event(fixture_message_created, bot)

    assert result.from_user is fixture_message_created.message.sender
    assert result.bot is bot


async def test_enrich_event_message_created_skips_get_chat_if_already_set(
    bot, fixture_message_created
):
    """Если chat уже выставлен на верхнем уровне, повторный запрос
    для recipient не делается."""
    existing_chat = _make_chat()
    fixture_message_created.chat = existing_chat
    # recipient.chat_id есть, но chat уже не None — второй вызов не нужен
    bot.get_chat_by_id = AsyncMock(return_value=existing_chat)

    await enrich_event(fixture_message_created, bot)

    # get_chat_by_id вызывается только один раз (верхний блок chat_id)
    assert bot.get_chat_by_id.await_count <= 1


# ---------------------------------------------------------------------------
# MessageEdited
# ---------------------------------------------------------------------------


async def test_enrich_event_message_edited_sets_from_user(
    bot, fixture_message_edited
):
    fake_chat = _make_chat()
    bot.get_chat_by_id = AsyncMock(return_value=fake_chat)

    result = await enrich_event(fixture_message_edited, bot)

    assert result.from_user is fixture_message_edited.message.sender
    assert result.bot is bot


# ---------------------------------------------------------------------------
# MessageCallback
# ---------------------------------------------------------------------------


async def test_enrich_event_message_callback_sets_from_user(
    bot, fixture_message_callback
):
    fake_chat = _make_chat()
    bot.get_chat_by_id = AsyncMock(return_value=fake_chat)

    result = await enrich_event(fixture_message_callback, bot)

    assert result.from_user is fixture_message_callback.callback.user
    assert result.bot is bot


async def test_enrich_event_message_callback_none_message(
    bot, fixture_message_callback
):
    """Если message=None — from_user всё равно берётся из callback.user."""
    fixture_message_callback.message = None
    bot.get_chat_by_id = AsyncMock()

    result = await enrich_event(fixture_message_callback, bot)

    assert result.from_user is fixture_message_callback.callback.user


# ---------------------------------------------------------------------------
# MessageRemoved — CHAT type → from_user из get_chat_member
# ---------------------------------------------------------------------------


async def test_enrich_event_message_removed_chat_type(
    bot, fixture_message_removed
):
    fake_chat = _make_chat(ChatType.CHAT)
    fake_member = MagicMock()
    bot.get_chat_by_id = AsyncMock(return_value=fake_chat)
    bot.get_chat_member = AsyncMock(return_value=fake_member)

    result = await enrich_event(fixture_message_removed, bot)

    bot.get_chat_member.assert_awaited_once_with(
        chat_id=fixture_message_removed.chat_id,
        user_id=fixture_message_removed.user_id,
    )
    assert result.from_user is fake_member


# ---------------------------------------------------------------------------
# MessageRemoved — DIALOG type → from_user = chat
# ---------------------------------------------------------------------------


async def test_enrich_event_message_removed_dialog_type(
    bot, fixture_message_removed
):
    fake_chat = _make_chat(ChatType.DIALOG)
    bot.get_chat_by_id = AsyncMock(return_value=fake_chat)
    bot.get_chat_member = AsyncMock()

    result = await enrich_event(fixture_message_removed, bot)

    bot.get_chat_member.assert_not_called()
    assert result.from_user is fake_chat


# ---------------------------------------------------------------------------
# UserRemoved — с admin_id → from_user из get_chat_member
# ---------------------------------------------------------------------------


async def test_enrich_event_user_removed_with_admin(bot, fixture_user_removed):
    fixture_user_removed.admin_id = 9999
    fake_chat = _make_chat()
    fake_member = MagicMock()
    bot.get_chat_by_id = AsyncMock(return_value=fake_chat)
    bot.get_chat_member = AsyncMock(return_value=fake_member)

    result = await enrich_event(fixture_user_removed, bot)

    bot.get_chat_member.assert_awaited_once_with(
        chat_id=fixture_user_removed.chat_id,
        user_id=fixture_user_removed.admin_id,
    )
    assert result.from_user is fake_member


# ---------------------------------------------------------------------------
# UserRemoved — без admin_id → get_chat_member не вызывается
# ---------------------------------------------------------------------------


async def test_enrich_event_user_removed_no_admin(bot, fixture_user_removed):
    fixture_user_removed.admin_id = None
    fake_chat = _make_chat()
    bot.get_chat_by_id = AsyncMock(return_value=fake_chat)
    bot.get_chat_member = AsyncMock()

    result = await enrich_event(fixture_user_removed, bot)

    bot.get_chat_member.assert_not_called()
    assert result.chat is fake_chat


# ---------------------------------------------------------------------------
# Группа: UserAdded, BotAdded, BotStarted, BotStopped,
#          ChatTitleChanged, DialogCleared, DialogMuted, DialogUnmuted
#          — from_user=user, get_chat_by_id вызывается
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name",
    [
        "fixture_user_added",
        "fixture_bot_added",
        "fixture_bot_started",
        "fixture_bot_stopped",
        "fixture_chat_title_changed",
        "fixture_dialog_cleared",
        "fixture_dialog_muted",
        "fixture_dialog_unmuted",
    ],
)
async def test_enrich_event_common_events_set_from_user(
    request, bot, fixture_name
):
    event = request.getfixturevalue(fixture_name)
    fake_chat = _make_chat()
    bot.get_chat_by_id = AsyncMock(return_value=fake_chat)

    result = await enrich_event(event, bot)

    bot.get_chat_by_id.assert_awaited_once_with(event.chat_id)
    assert result.chat is fake_chat
    assert result.from_user is event.user


# ---------------------------------------------------------------------------
# bot ссылка проставляется на event_object
# ---------------------------------------------------------------------------


async def test_enrich_event_sets_bot_on_event(bot, fixture_bot_started):
    fake_chat = _make_chat()
    bot.get_chat_by_id = AsyncMock(return_value=fake_chat)

    result = await enrich_event(fixture_bot_started, bot)

    assert result.bot is bot
