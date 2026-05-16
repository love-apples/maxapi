from maxapi import enums
from maxapi import types as types_module
from maxapi.methods import types as method_types
from maxapi.types import (
    AttachmentPayload,
    AttachmentUpload,
    Callback,
    Chat,
    MessageBody,
    SendedMessage,
    User,
    attachments,
)


def test_common_types_are_reexported_from_maxapi_types():
    from maxapi.methods.types.sended_message import (
        SendedMessage as DirectSendedMessage,
    )
    from maxapi.types.attachments.upload import (
        AttachmentPayload as DirectPayload,
    )
    from maxapi.types.attachments.upload import (
        AttachmentUpload as DirectUpload,
    )
    from maxapi.types.callback import Callback as DirectCallback
    from maxapi.types.chats import Chat as DirectChat
    from maxapi.types.message import MessageBody as DirectMessageBody
    from maxapi.types.users import User as DirectUser

    assert AttachmentPayload is DirectPayload
    assert AttachmentUpload is DirectUpload
    assert Callback is DirectCallback
    assert Chat is DirectChat
    assert MessageBody is DirectMessageBody
    assert SendedMessage is DirectSendedMessage
    assert User is DirectUser


def test_unknown_lazy_type_export_raises_attribute_error():
    import pytest

    with pytest.raises(AttributeError):
        types_module.__getattr__("UnknownType")


def test_attachment_types_are_reexported_from_attachment_package():
    from maxapi.types.attachments.attachment import (
        ButtonsPayload as DirectButtonsPayload,
    )
    from maxapi.types.attachments.buttons.attachment_button import (
        AttachmentButton as DirectAttachmentButton,
    )
    from maxapi.types.attachments.buttons.callback_button import (
        CallbackButton as DirectCallbackButton,
    )
    from maxapi.types.attachments.upload import (
        AttachmentUpload as DirectUpload,
    )

    assert attachments.AttachmentButton is DirectAttachmentButton
    assert attachments.AttachmentUpload is DirectUpload
    assert attachments.ButtonsPayload is DirectButtonsPayload
    assert attachments.CallbackButton is DirectCallbackButton


def test_enums_are_reexported_from_enum_package():
    from maxapi.enums.attachment import AttachmentType
    from maxapi.enums.chat_type import ChatType
    from maxapi.enums.message_link_type import MessageLinkType
    from maxapi.enums.update import UpdateType
    from maxapi.enums.upload_type import UploadType

    assert enums.AttachmentType is AttachmentType
    assert enums.ChatType is ChatType
    assert enums.MessageLinkType is MessageLinkType
    assert enums.UpdateType is UpdateType
    assert enums.UploadType is UploadType


def test_method_result_types_are_reexported_from_methods_types():
    from maxapi.methods.types.added_members_chat import AddedMembersChat
    from maxapi.methods.types.edited_message import EditedMessage
    from maxapi.methods.types.getted_upload_url import GettedUploadUrl
    from maxapi.methods.types.sended_message import (
        SendedMessage as DirectSendedMessage,
    )

    assert method_types.AddedMembersChat is AddedMembersChat
    assert method_types.EditedMessage is EditedMessage
    assert method_types.GettedUploadUrl is GettedUploadUrl
    assert method_types.SendedMessage is DirectSendedMessage
