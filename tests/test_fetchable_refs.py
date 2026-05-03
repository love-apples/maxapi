from unittest.mock import MagicMock

import pytest
from maxapi.enums.update import UpdateType
from maxapi.types.fetchable import LazyRef
from maxapi.types.updates.base_update import BaseUpdate


class DummyUpdate(BaseUpdate):
    update_type: UpdateType = UpdateType.BOT_STARTED


def test_lazy_ref_pending_attr_error_and_repr(bot):
    ref = LazyRef(
        bot=bot,
        fetcher=MagicMock(),
        setter=MagicMock(),
        description="chat_id=1",
    )

    assert not ref
    assert "pending" in repr(ref)

    with pytest.raises(AttributeError, match=r"ref\.fetch\(\)"):
        _ = ref.title


def test_lazy_ref_fetch_caches_and_exposes_attributes(bot):
    resolved = type("Resolved", (), {"title": "chat-title"})()
    fetcher = MagicMock(return_value=resolved)
    setter = MagicMock()
    ref = LazyRef(
        bot=bot,
        fetcher=fetcher,
        setter=setter,
        description="chat_id=123",
    )

    first = ref.fetch()
    second = ref.fetch()

    assert first is resolved
    assert second is resolved
    assert ref.title == "chat-title"
    assert ref
    assert "resolved" in repr(ref)
    fetcher.assert_called_once()
    setter.assert_called_once_with(resolved)


def test_base_update_fetch_chat_handles_none():
    event = DummyUpdate(timestamp=1)
    assert event.fetch_chat() is None


def test_base_update_fetch_chat_returns_existing_value():
    event = DummyUpdate(timestamp=1)
    chat = object()
    event.chat = chat

    assert event.fetch_chat() is chat


def test_base_update_fetch_chat_ignores_non_lazy_fetch_method():
    class ChatLike:
        def __init__(self) -> None:
            self.fetch_called = False

        def fetch(self):
            self.fetch_called = True
            return "unexpected"

    event = DummyUpdate(timestamp=1)
    chat = ChatLike()
    event.chat = chat

    assert event.fetch_chat() is chat
    assert not chat.fetch_called


def test_base_update_fetch_chat_handles_lazy_ref(bot):
    resolved = object()
    event = DummyUpdate(timestamp=1)
    event.chat = LazyRef(
        bot=bot,
        fetcher=MagicMock(return_value=resolved),
        setter=MagicMock(),
        description="chat_id=7",
    )

    assert event.fetch_chat() is resolved


def test_base_update_fetch_from_user_handles_none():
    event = DummyUpdate(timestamp=1)
    assert event.fetch_from_user() is None


def test_base_update_fetch_from_user_returns_existing_value():
    event = DummyUpdate(timestamp=1)
    from_user = object()
    event.from_user = from_user

    assert event.fetch_from_user() is from_user


def test_base_update_fetch_from_user_ignores_non_lazy_fetch_method():
    class UserLike:
        def __init__(self) -> None:
            self.fetch_called = False

        def fetch(self):
            self.fetch_called = True
            return "unexpected"

    event = DummyUpdate(timestamp=1)
    from_user = UserLike()
    event.from_user = from_user

    assert event.fetch_from_user() is from_user
    assert not from_user.fetch_called


def test_base_update_fetch_from_user_handles_lazy_ref(bot):
    resolved = object()
    event = DummyUpdate(timestamp=1)
    event.from_user = LazyRef(
        bot=bot,
        fetcher=MagicMock(return_value=resolved),
        setter=MagicMock(),
        description="user_id=9",
    )

    assert event.fetch_from_user() is resolved


def test_base_update_fetch_field_unknown_field_raises_clear_error():
    event = DummyUpdate(timestamp=1)

    with pytest.raises(AttributeError, match=r"has no field 'missing'"):
        event._fetch_field("missing")
