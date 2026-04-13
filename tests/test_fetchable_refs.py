import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from maxapi.enums.update import UpdateType
from maxapi.types.fetchable import LazyRef
from maxapi.types.updates.base_update import BaseUpdate


class DummyUpdate(BaseUpdate):
    update_type: UpdateType = UpdateType.BOT_STARTED


async def test_lazy_ref_pending_attr_error_and_repr(bot):
    ref = LazyRef(
        bot=bot,
        fetcher=AsyncMock(),
        setter=MagicMock(),
        description="chat_id=1",
    )

    assert not ref
    assert "pending" in repr(ref)

    with pytest.raises(AttributeError, match=r"await ref\.fetch\(\)"):
        _ = ref.title


async def test_lazy_ref_fetch_caches_and_exposes_attributes(bot):
    resolved = type("Resolved", (), {"title": "chat-title"})()
    fetcher = AsyncMock(return_value=resolved)
    setter = MagicMock()
    ref = LazyRef(
        bot=bot,
        fetcher=fetcher,
        setter=setter,
        description="chat_id=123",
    )

    first = await ref.fetch()
    second = await ref.fetch()

    assert first is resolved
    assert second is resolved
    assert ref.title == "chat-title"
    assert ref
    assert "resolved" in repr(ref)
    fetcher.assert_awaited_once()
    setter.assert_called_once_with(resolved)


async def test_lazy_ref_fetch_is_concurrency_safe(bot):
    resolved = type("Resolved", (), {"title": "chat-title"})()
    setter = MagicMock()
    started = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def fetcher():
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return resolved

    ref = LazyRef(
        bot=bot,
        fetcher=fetcher,
        setter=setter,
        description="chat_id=123",
    )

    first_task = asyncio.create_task(ref.fetch())
    await started.wait()
    second_task = asyncio.create_task(ref.fetch())
    release.set()

    first, second = await asyncio.gather(first_task, second_task)

    assert first is resolved
    assert second is resolved
    assert calls == 1
    setter.assert_called_once_with(resolved)


async def test_base_update_fetch_chat_handles_none():
    event = DummyUpdate(timestamp=1)
    assert await event.fetch_chat() is None


async def test_base_update_fetch_chat_returns_existing_value():
    event = DummyUpdate(timestamp=1)
    chat = object()
    event.chat = chat

    assert await event.fetch_chat() is chat


async def test_base_update_fetch_chat_ignores_non_lazy_fetch_method():
    class ChatLike:
        def __init__(self) -> None:
            self.fetch_called = False

        async def fetch(self):
            self.fetch_called = True
            return "unexpected"

    event = DummyUpdate(timestamp=1)
    chat = ChatLike()
    event.chat = chat

    assert await event.fetch_chat() is chat
    assert not chat.fetch_called


async def test_base_update_fetch_chat_awaits_lazy_ref(bot):
    resolved = object()
    event = DummyUpdate(timestamp=1)
    event.chat = LazyRef(
        bot=bot,
        fetcher=AsyncMock(return_value=resolved),
        setter=MagicMock(),
        description="chat_id=7",
    )

    assert await event.fetch_chat() is resolved


async def test_base_update_fetch_from_user_handles_none():
    event = DummyUpdate(timestamp=1)
    assert await event.fetch_from_user() is None


async def test_base_update_fetch_from_user_returns_existing_value():
    event = DummyUpdate(timestamp=1)
    from_user = object()
    event.from_user = from_user

    assert await event.fetch_from_user() is from_user


async def test_base_update_fetch_from_user_ignores_non_lazy_fetch_method():
    class UserLike:
        def __init__(self) -> None:
            self.fetch_called = False

        async def fetch(self):
            self.fetch_called = True
            return "unexpected"

    event = DummyUpdate(timestamp=1)
    from_user = UserLike()
    event.from_user = from_user

    assert await event.fetch_from_user() is from_user
    assert not from_user.fetch_called


async def test_base_update_fetch_from_user_awaits_lazy_ref(bot):
    resolved = object()
    event = DummyUpdate(timestamp=1)
    event.from_user = LazyRef(
        bot=bot,
        fetcher=AsyncMock(return_value=resolved),
        setter=MagicMock(),
        description="user_id=9",
    )

    assert await event.fetch_from_user() is resolved


async def test_base_update_fetch_field_unknown_field_raises_clear_error():
    event = DummyUpdate(timestamp=1)

    with pytest.raises(AttributeError, match=r"has no field 'missing'"):
        await event._fetch_field("missing")
