from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from maxapi.connection.base import BaseConnection
from maxapi.enums.add_chat_members_error_code import AddChatMembersErrorCode
from maxapi.enums.attachment import AttachmentType
from maxapi.enums.chat_permission import ChatPermission
from maxapi.enums.text_style import TextStyle
from maxapi.methods.add_admin_chat import AddAdminChat
from maxapi.methods.get_chat_by_link import GetChatByLink
from maxapi.methods.get_messages import GetMessages
from maxapi.methods.types.added_members_chat import AddedMembersChat
from maxapi.types.attachments.attachment import ContactAttachmentPayload
from maxapi.types.attachments.image import PhotoAttachmentRequestPayload
from maxapi.types.attachments.video import Video
from maxapi.types.chats import ChatMember
from maxapi.types.message import MessageBody
from maxapi.types.users import ChatAdmin, User
from pydantic import ValidationError


def test_added_members_chat_error_code_enum_accepts_known_code():
    payload = {
        "success": False,
        "message": "error",
        "failed_user_ids": [1, 2],
        "failed_user_details": [
            {
                "error_code": (
                    AddChatMembersErrorCode.ADD_PARTICIPANT_PRIVACY.value
                ),
                "user_ids": [1],
            }
        ],
    }

    obj = AddedMembersChat.model_validate(payload)
    assert obj.failed_user_details is not None
    assert (
        obj.failed_user_details[0].error_code
        == AddChatMembersErrorCode.ADD_PARTICIPANT_PRIVACY
    )


def test_added_members_chat_error_code_enum_rejects_unknown_code():
    payload = {
        "success": False,
        "message": "error",
        "failed_user_ids": [1],
        "failed_user_details": [
            {
                "error_code": "unknown.code",
                "user_ids": [1],
            }
        ],
    }

    with pytest.raises(ValidationError):
        AddedMembersChat.model_validate(payload)


def test_chat_permission_accepts_swagger_admin_values():
    swagger_values = {
        "read_all_messages",
        "add_remove_members",
        "add_admins",
        "change_chat_info",
        "pin_message",
        "write",
        "can_call",
        "edit_link",
        "post_edit_delete_message",
        "edit_message",
        "delete_message",
        "edit",
        "delete",
    }

    assert {ChatPermission(value).value for value in swagger_values} == (
        swagger_values
    )
    assert ChatPermission.VIEW_STATS.value == "view_stats"


def test_user_and_chat_admin_keep_swagger_compat_fields():
    user = User.model_validate(
        {
            "user_id": 1,
            "first_name": "Alice",
            "username": None,
            "is_bot": False,
            "last_activity_time": 0,
        }
    )
    admin = ChatAdmin.model_validate(
        {
            "user_id": 1,
            "permissions": ["read_all_messages"],
            "alias": "owner",
        }
    )

    assert user.first_name == "Alice"
    assert admin.alias == "owner"


def test_chat_member_accepts_swagger_fields_with_nullable_permissions():
    member = ChatMember.model_validate(
        {
            "user_id": 1,
            "first_name": "Alice",
            "username": "alice",
            "is_bot": False,
            "last_activity_time": 0,
            "last_access_time": 10,
            "is_owner": False,
            "is_admin": True,
            "join_time": 20,
            "permissions": None,
            "alias": "moderator",
        }
    )

    assert member.last_access_time == 10
    assert member.is_owner is False
    assert member.is_admin is True
    assert member.join_time == 20
    assert member.permissions is None
    assert member.alias == "moderator"


def test_get_messages_requires_chat_id_or_message_ids(bot):
    with pytest.raises(ValueError, match="chat_id или message_ids"):
        GetMessages(bot=bot)


def test_get_messages_rejects_chat_id_with_message_ids(bot):
    with pytest.raises(ValueError, match="chat_id или message_ids"):
        GetMessages(bot=bot, chat_id=1, message_ids=["mid-1"])


async def test_get_messages_sends_message_ids_as_comma_list(bot):
    method = GetMessages(
        bot=bot,
        message_ids=["mid-1", "mid-2"],
    )

    with patch.object(
        BaseConnection, "request", new=AsyncMock(return_value=Mock())
    ) as mocked_request:
        await method.fetch()

    params = mocked_request.call_args.kwargs["params"]
    assert params["message_ids"] == "mid-1,mid-2"
    assert "chat_id" not in params


async def test_get_messages_sends_datetime_bounds_as_unix_seconds(bot):
    from_time = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    to_time = datetime(2026, 1, 3, 3, 4, 5, tzinfo=timezone.utc)
    method = GetMessages(
        bot=bot,
        chat_id=1,
        from_time=from_time,
        to_time=to_time,
    )

    with patch.object(
        BaseConnection, "request", new=AsyncMock(return_value=Mock())
    ) as mocked_request:
        await method.fetch()

    params = mocked_request.call_args.kwargs["params"]
    assert params["from"] == int(from_time.timestamp())
    assert params["to"] == int(to_time.timestamp())


async def test_get_messages_omits_none_count(bot):
    method = GetMessages(bot=bot, chat_id=1, count=None)

    with patch.object(
        BaseConnection, "request", new=AsyncMock(return_value=Mock())
    ) as mocked_request:
        await method.fetch()

    params = mocked_request.call_args.kwargs["params"]
    assert "count" not in params


async def test_add_admin_chat_sends_only_admins_payload(bot):
    admin = ChatAdmin(
        user_id=1,
        permissions=[ChatPermission.READ_ALL_MESSAGES],
    )
    method = AddAdminChat(bot=bot, chat_id=123, admins=[admin])

    with patch.object(
        BaseConnection, "request", new=AsyncMock(return_value=Mock())
    ) as mocked_request:
        await method.fetch()

    payload = mocked_request.call_args.kwargs["json"]
    assert set(payload) == {"admins"}
    assert payload["admins"] == [admin.model_dump()]


async def test_add_admin_chat_ignores_deprecated_marker(bot):
    admin = ChatAdmin(
        user_id=1,
        permissions=[ChatPermission.READ_ALL_MESSAGES],
    )

    with pytest.warns(DeprecationWarning, match="marker"):
        method = AddAdminChat(
            bot=bot,
            chat_id=123,
            admins=[admin],
            marker=42,
        )

    with patch.object(
        BaseConnection, "request", new=AsyncMock(return_value=Mock())
    ) as mocked_request:
        await method.fetch()

    payload = mocked_request.call_args.kwargs["json"]
    assert "marker" not in payload


async def test_bot_add_list_admin_chat_ignores_deprecated_marker(bot):
    admin = ChatAdmin(
        user_id=1,
        permissions=[ChatPermission.READ_ALL_MESSAGES],
    )

    with (
        patch.object(
            BaseConnection, "request", new=AsyncMock(return_value=Mock())
        ) as mocked_request,
        pytest.warns(DeprecationWarning, match="marker"),
    ):
        await bot.add_list_admin_chat(
            chat_id=123,
            admins=[admin],
            marker=42,
        )

    payload = mocked_request.call_args.kwargs["json"]
    assert "marker" not in payload


@pytest.mark.parametrize(
    ("link", "expected_path"),
    [
        ("channel", "/chats/channel"),
        ("@channel", "/chats/@channel"),
        ("https://max.ru/channel", "/chats/channel"),
    ],
)
async def test_get_chat_by_link_normalizes_public_link(
    bot,
    link,
    expected_path,
):
    with pytest.warns(DeprecationWarning, match="GetChatByLink"):
        method = GetChatByLink(bot=bot, link=link)

    with patch.object(
        BaseConnection, "request", new=AsyncMock(return_value=Mock())
    ) as mocked_request:
        await method.fetch()

    assert mocked_request.call_args.kwargs["path"] == expected_path


@pytest.mark.parametrize(
    "link",
    [
        "",
        "not a link",
        "https://max.ru/",
        "https://max.ru/channel/extra invalid",
    ],
)
def test_get_chat_by_link_rejects_invalid_link(bot, link):
    with (
        pytest.warns(DeprecationWarning, match="GetChatByLink"),
        pytest.raises(ValueError, match="link не соответствует"),
    ):
        GetChatByLink(bot=bot, link=link)


async def test_get_chat_by_link_keeps_valid_link_characters(bot):
    with pytest.warns(DeprecationWarning, match="GetChatByLink"):
        method = GetChatByLink(bot=bot, link="channel-name_123")

    with patch.object(
        BaseConnection, "request", new=AsyncMock(return_value=Mock())
    ) as mocked_request:
        await method.fetch()

    assert mocked_request.call_args.kwargs["path"] == (
        "/chats/channel-name_123"
    )


async def test_bot_get_chat_by_link_warns_about_deprecation(bot):
    """Проверить предупреждение публичной обёртки устаревшего метода."""
    with (
        patch(
            "maxapi.bot.GetChatByLink.fetch",
            new=AsyncMock(return_value=Mock()),
        ) as mocked_fetch,
        pytest.warns(DeprecationWarning, match="get_chat_by_link"),
    ):
        await bot.get_chat_by_link("channel")

    mocked_fetch.assert_awaited_once_with()


def test_contact_payload_accepts_hash_and_nullable_vcf():
    payload = ContactAttachmentPayload.model_validate(
        {"vcf_info": None, "hash": "contact-hash", "max_info": None}
    )

    assert payload.hash == "contact-hash"
    assert payload.vcf.full_name is None


def test_photo_request_payload_accepts_swagger_photos_shape():
    payload = PhotoAttachmentRequestPayload(
        photos={"640x480": {"token": "image-token"}}
    )

    assert payload.model_dump()["photos"]["640x480"]["token"] == (
        "image-token"
    )


def test_get_video_details_payload_validates_without_attachment_type():
    video = Video.model_validate(
        {
            "token": "video-token",
            "urls": {"mp4_720": "https://example.com/video.mp4"},
            "thumbnail": {
                "photo_id": 10,
                "token": "thumb-token",
                "url": "https://example.com/thumb.jpg",
            },
            "width": 1280,
            "height": 720,
            "duration": 30,
        }
    )

    assert video.type == AttachmentType.VIDEO
    assert video.token == "video-token"
    assert video.thumbnail is not None
    assert video.thumbnail.token == "thumb-token"


def test_highlighted_markup_roundtrip_to_text_helpers():
    body = MessageBody.model_validate(
        {
            "mid": "msg.highlight",
            "seq": 1,
            "text": "important",
            "markup": [
                {"type": TextStyle.HIGHLIGHTED, "from": 0, "length": 9}
            ],
        }
    )

    assert body.html_text == "<mark>important</mark>"
    assert body.md_text == "^^important^^"


def test_quote_markup_roundtrip_to_text_helpers():
    body = MessageBody.model_validate(
        {
            "mid": "msg.quote",
            "seq": 1,
            "text": "quote",
            "markup": [{"type": TextStyle.QUOTE, "from": 0, "length": 5}],
        }
    )

    assert body.html_text == "<blockquote>quote</blockquote>"
    assert body.md_text == "> quote"
