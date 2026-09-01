"""Тесты методов работы с комментариями к постам в каналах."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from maxapi.connection.base import BaseConnection
from maxapi.enums.http_method import HTTPMethod
from maxapi.enums.message_link_type import MessageLinkType
from maxapi.enums.parse_mode import TextFormat
from maxapi.methods.delete_comment import DeleteComment
from maxapi.methods.edit_comment import EditComment
from maxapi.methods.get_comment import GetComment
from maxapi.methods.get_comments import GetComments
from maxapi.methods.send_comment import SendComment
from maxapi.methods.types.deleted_comment import DeletedComment
from maxapi.methods.types.edited_comment import EditedComment
from maxapi.methods.types.sended_comment import SendedComment
from maxapi.types import CommentMessage, Comments, NewMessageLink

MESSAGE_ID = "mid.post123"
COMMENT_ID = "mid.comment456"

COMMENT_PAYLOAD = {
    "sender": {
        "user_id": 1,
        "first_name": "Тест",
        "is_bot": False,
        "last_activity_time": 0,
    },
    "recipient": {"chat_id": 10, "chat_type": "chat"},
    "timestamp": 1756704000000,
    "link": {
        "type": "reply",
        "message": {"mid": "mid.parent", "seq": 1, "text": "родитель"},
    },
    "body": {
        "mid": COMMENT_ID,
        "seq": 2,
        "text": "жирный текст",
        "markup": [{"type": "strong", "from": 0, "length": 6}],
    },
}


def _patched_request(return_value=None):
    return patch.object(
        BaseConnection,
        "request",
        new=AsyncMock(
            return_value=Mock() if return_value is None else return_value
        ),
    )


async def test_get_comments_builds_pagination_params(bot):
    method = GetComments(
        bot=bot,
        message_id=MESSAGE_ID,
        after=1000,
        before=2000,
        count=25,
    )

    with _patched_request(
        Comments(messages=[COMMENT_PAYLOAD])
    ) as mocked_request:
        comments = await method.fetch()

    kwargs = mocked_request.call_args.kwargs
    assert kwargs["method"] == HTTPMethod.GET
    assert kwargs["path"] == f"/messages/{MESSAGE_ID}/comments"
    assert kwargs["params"]["after"] == 1000
    assert kwargs["params"]["before"] == 2000
    assert kwargs["params"]["count"] == 25
    assert "comment_ids" not in kwargs["params"]
    assert comments.messages[0].post_message_id == MESSAGE_ID


async def test_get_comments_by_ids_omits_pagination(bot):
    method = GetComments(
        bot=bot,
        message_id=MESSAGE_ID,
        comment_ids=["mid.a", "mid.b"],
        after=1000,
        count=25,
    )

    with _patched_request(Comments(messages=[])) as mocked_request:
        await method.fetch()

    params = mocked_request.call_args.kwargs["params"]
    assert params["comment_ids"] == "mid.a,mid.b"
    assert "after" not in params
    assert "before" not in params
    assert "count" not in params


async def test_get_comments_validates_empty_comment_ids(bot):
    with pytest.raises(ValueError, match="comment_ids"):
        GetComments(bot=bot, message_id=MESSAGE_ID, comment_ids=[])


async def test_get_comments_converts_datetime_to_milliseconds(bot):
    moment = datetime(2026, 9, 1, tzinfo=timezone.utc)

    method = GetComments(bot=bot, message_id=MESSAGE_ID, after=moment)

    with _patched_request(Comments(messages=[])) as mocked_request:
        await method.fetch()

    params = mocked_request.call_args.kwargs["params"]
    assert params["after"] == int(moment.timestamp() * 1000)


@pytest.mark.parametrize("count", [0, 101])
async def test_get_comments_validates_count(bot, count):
    with pytest.raises(ValueError, match="count"):
        GetComments(bot=bot, message_id=MESSAGE_ID, count=count)


async def test_get_comments_validates_message_id(bot):
    with pytest.raises(ValueError, match="message_id"):
        GetComments(bot=bot, message_id="")


async def test_get_comment_builds_path(bot):
    method = GetComment(bot=bot, message_id=MESSAGE_ID, comment_id=COMMENT_ID)

    with _patched_request(CommentMessage(**COMMENT_PAYLOAD)) as mocked_request:
        comment = await method.fetch()

    kwargs = mocked_request.call_args.kwargs
    assert kwargs["method"] == HTTPMethod.GET
    assert kwargs["path"] == (f"/messages/{MESSAGE_ID}/comments/{COMMENT_ID}")
    assert comment.post_message_id == MESSAGE_ID


async def test_send_comment_builds_json(bot):
    method = SendComment(
        bot=bot,
        message_id=MESSAGE_ID,
        text="привет",
        link=NewMessageLink(type=MessageLinkType.REPLY, mid="mid.parent"),
        format="markdown",
    )

    with _patched_request(
        SendedComment(message=COMMENT_PAYLOAD)
    ) as mocked_request:
        sended = await method.fetch()

    kwargs = mocked_request.call_args.kwargs
    assert kwargs["method"] == HTTPMethod.POST
    assert kwargs["path"] == f"/messages/{MESSAGE_ID}/comments"
    assert kwargs["json"]["text"] == "привет"
    assert kwargs["json"]["link"]["mid"] == "mid.parent"
    assert kwargs["json"]["format"] == TextFormat.MARKDOWN
    assert sended.message.post_message_id == MESSAGE_ID


async def test_send_comment_validates_text_length(bot):
    with pytest.raises(ValueError, match="text"):
        SendComment(bot=bot, message_id=MESSAGE_ID, text="a" * 4000)


async def test_send_comment_requires_text_or_link(bot):
    with pytest.raises(ValueError, match="text или link"):
        SendComment(bot=bot, message_id=MESSAGE_ID)


async def test_edit_comment_builds_params_and_json(bot):
    method = EditComment(
        bot=bot,
        message_id=MESSAGE_ID,
        comment_id=COMMENT_ID,
        text="новый текст",
    )

    with _patched_request() as mocked_request:
        await method.fetch()

    kwargs = mocked_request.call_args.kwargs
    assert kwargs["method"] == HTTPMethod.PUT
    assert kwargs["path"] == f"/messages/{MESSAGE_ID}/comments"
    assert kwargs["params"]["comment_id"] == COMMENT_ID
    assert kwargs["json"] == {"text": "новый текст"}


async def test_delete_comment_builds_params(bot):
    method = DeleteComment(
        bot=bot, message_id=MESSAGE_ID, comment_id=COMMENT_ID
    )

    with _patched_request() as mocked_request:
        await method.fetch()

    kwargs = mocked_request.call_args.kwargs
    assert kwargs["method"] == HTTPMethod.DELETE
    assert kwargs["path"] == f"/messages/{MESSAGE_ID}/comments"
    assert kwargs["params"]["comment_id"] == COMMENT_ID


async def test_delete_comment_validates_comment_id(bot):
    with pytest.raises(ValueError, match="comment_id"):
        DeleteComment(bot=bot, message_id=MESSAGE_ID, comment_id="")


@pytest.mark.parametrize(
    "factory",
    [
        lambda bot: SendComment(bot=bot, message_id="", text="привет"),
        lambda bot: EditComment(
            bot=bot, message_id="", comment_id=COMMENT_ID, text="привет"
        ),
        lambda bot: DeleteComment(
            bot=bot, message_id="", comment_id=COMMENT_ID
        ),
        lambda bot: GetComment(bot=bot, message_id="", comment_id=COMMENT_ID),
    ],
)
async def test_methods_validate_empty_message_id(bot, factory):
    with pytest.raises(ValueError, match="message_id"):
        factory(bot)


@pytest.mark.parametrize(
    "factory",
    [
        lambda bot: EditComment(
            bot=bot, message_id=MESSAGE_ID, comment_id="", text="привет"
        ),
        lambda bot: GetComment(bot=bot, message_id=MESSAGE_ID, comment_id=""),
    ],
)
async def test_methods_validate_empty_comment_id(bot, factory):
    with pytest.raises(ValueError, match="comment_id"):
        factory(bot)


async def test_edit_comment_validates_text_length(bot):
    with pytest.raises(ValueError, match="text"):
        EditComment(
            bot=bot,
            message_id=MESSAGE_ID,
            comment_id=COMMENT_ID,
            text="a" * 4000,
        )


async def test_edit_comment_with_link_and_string_format(bot):
    method = EditComment(
        bot=bot,
        message_id=MESSAGE_ID,
        comment_id=COMMENT_ID,
        text="привет",
        link=NewMessageLink(type=MessageLinkType.REPLY, mid="mid.parent"),
        format="html",
    )

    with _patched_request(EditedComment(success=True)) as mocked_request:
        await method.fetch()

    json = mocked_request.call_args.kwargs["json"]
    assert json["link"]["mid"] == "mid.parent"
    assert json["format"] == TextFormat.HTML


async def test_bot_get_comments_wrapper(bot):
    with _patched_request(Comments(messages=[])) as mocked_request:
        await bot.get_comments(message_id=MESSAGE_ID, after=1000)

    kwargs = mocked_request.call_args.kwargs
    assert kwargs["path"] == f"/messages/{MESSAGE_ID}/comments"
    assert kwargs["params"]["after"] == 1000


async def test_bot_get_comment_wrapper(bot):
    with _patched_request(CommentMessage(**COMMENT_PAYLOAD)) as mocked:
        comment = await bot.get_comment(
            message_id=MESSAGE_ID, comment_id=COMMENT_ID
        )

    assert mocked.call_args.kwargs["path"] == (
        f"/messages/{MESSAGE_ID}/comments/{COMMENT_ID}"
    )
    assert comment.post_message_id == MESSAGE_ID


def test_comment_message_parses_payload():
    comment = CommentMessage(**COMMENT_PAYLOAD)

    assert comment.sender is not None
    assert comment.sender.user_id == 1
    assert comment.body.mid == COMMENT_ID
    assert comment.link is not None
    assert comment.link.type == MessageLinkType.REPLY
    assert comment.link.message.mid == "mid.parent"


def test_comment_message_body_markup_decoding():
    comment = CommentMessage(**COMMENT_PAYLOAD)

    assert comment.body.html_text == "<b>жирный</b> текст"


def test_comments_parses_list():
    comments = Comments(messages=[COMMENT_PAYLOAD])

    assert len(comments.messages) == 1
    assert comments.messages[0].body.seq == 2


async def test_bot_send_comment_uses_default_format(bot):
    bot.parse_mode = TextFormat.HTML

    with _patched_request() as mocked_request:
        await bot.send_comment(message_id=MESSAGE_ID, text="привет")

    assert mocked_request.call_args.kwargs["json"]["format"] == TextFormat.HTML


def _enriched_comment(bot):
    comment = CommentMessage(**COMMENT_PAYLOAD)
    comment.bot = bot
    comment.post_message_id = MESSAGE_ID
    return comment


async def test_comment_reply_shortcut(bot):
    comment = _enriched_comment(bot)

    with _patched_request(
        SendedComment(message=COMMENT_PAYLOAD)
    ) as mocked_request:
        await comment.reply("ответ")

    kwargs = mocked_request.call_args.kwargs
    assert kwargs["method"] == HTTPMethod.POST
    assert kwargs["path"] == f"/messages/{MESSAGE_ID}/comments"
    assert kwargs["json"]["text"] == "ответ"
    assert kwargs["json"]["link"]["type"] == MessageLinkType.REPLY
    assert kwargs["json"]["link"]["mid"] == COMMENT_ID


async def test_comment_edit_shortcut(bot):
    comment = _enriched_comment(bot)

    with _patched_request(EditedComment(success=True)) as mocked_request:
        await comment.edit("новый текст")

    kwargs = mocked_request.call_args.kwargs
    assert kwargs["method"] == HTTPMethod.PUT
    assert kwargs["path"] == f"/messages/{MESSAGE_ID}/comments"
    assert kwargs["params"]["comment_id"] == COMMENT_ID
    assert kwargs["json"] == {"text": "новый текст"}


async def test_comment_delete_shortcut(bot):
    comment = _enriched_comment(bot)

    with _patched_request(DeletedComment(success=True)) as mocked_request:
        await comment.delete()

    kwargs = mocked_request.call_args.kwargs
    assert kwargs["method"] == HTTPMethod.DELETE
    assert kwargs["path"] == f"/messages/{MESSAGE_ID}/comments"
    assert kwargs["params"]["comment_id"] == COMMENT_ID


async def test_comment_shortcut_without_post_message_id(bot):
    comment = CommentMessage(**COMMENT_PAYLOAD)
    comment.bot = bot

    with pytest.raises(ValueError, match="message_id поста"):
        await comment.delete()


async def test_comment_shortcut_without_bot():
    comment = CommentMessage(**COMMENT_PAYLOAD)
    comment.post_message_id = MESSAGE_ID

    with pytest.raises(RuntimeError, match="Bot не инициализирован"):
        await comment.delete()


def test_comment_result_types_are_reexported():
    from maxapi.methods import types as method_types
    from maxapi.types import (
        DeletedComment as LazyDeletedComment,
    )
    from maxapi.types import (
        EditedComment as LazyEditedComment,
    )
    from maxapi.types import (
        SendedComment as LazySendedComment,
    )

    assert method_types.DeletedComment is DeletedComment
    assert method_types.EditedComment is EditedComment
    assert method_types.SendedComment is SendedComment
    assert LazyDeletedComment is DeletedComment
    assert LazyEditedComment is EditedComment
    assert LazySendedComment is SendedComment
