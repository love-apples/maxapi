import pytest
from maxapi.enums.add_chat_members_error_code import AddChatMembersErrorCode
from maxapi.enums.attachment import AttachmentType
from maxapi.enums.chat_permission import ChatPermission
from maxapi.enums.text_style import TextStyle
from maxapi.methods.types.added_members_chat import AddedMembersChat
from maxapi.types.attachments.attachment import ContactAttachmentPayload
from maxapi.types.attachments.image import PhotoAttachmentRequestPayload
from maxapi.types.attachments.video import Video
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
    assert (
        ChatPermission.POST_EDIT_DELETE_MESSAGE.value
        == "post_edit_delete_message"
    )
    assert ChatPermission.EDIT_MESSAGE.value == "edit_message"
    assert ChatPermission.DELETE_MESSAGE.value == "delete_message"

    assert ChatPermission.EDIT.value == "edit"
    assert ChatPermission.DELETE.value == "delete"
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
