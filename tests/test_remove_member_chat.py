from unittest.mock import AsyncMock, Mock, patch

import pytest
from maxapi.connection.base import BaseConnection
from maxapi.methods.remove_member_chat import RemoveMemberChat


@pytest.mark.parametrize(
    ("block", "expected"),
    [(True, "true"), (False, "false")],
)
async def test_remove_member_chat_serializes_block_in_params(
    bot, block, expected
):
    """block уходит в query как "true"/"false"."""
    method = RemoveMemberChat(bot=bot, chat_id=1, user_id=2, block=block)

    with patch.object(
        BaseConnection, "request", new=AsyncMock(return_value=Mock())
    ) as mocked_request:
        await method.fetch()

    params = mocked_request.call_args.kwargs["params"]
    assert params["block"] == expected
    assert params["chat_id"] == 1
    assert params["user_id"] == 2
