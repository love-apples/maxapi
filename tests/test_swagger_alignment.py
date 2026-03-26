import pytest
from maxapi.enums.add_chat_members_error_code import AddChatMembersErrorCode
from maxapi.methods.types.added_members_chat import AddedMembersChat
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
