"""Тесты для типов и моделей."""

# Core Stuff
from datetime import datetime
from typing import Any, ClassVar

from maxapi.enums.attachment import AttachmentType
from maxapi.enums.message_link_type import MessageLinkType
from maxapi.enums.upload_type import UploadType
from maxapi.types import (
    BotCommand,
    CallbackButton,
    ChatButton,
    LinkButton,
    RequestContactButton,
    RequestGeoLocationButton,
)
from maxapi.types.input_media import InputMediaBuffer
from maxapi.types.message import NewMessageLink


class TestButtons:
    """Тесты для кнопок."""

    def test_callback_button(self):
        """Тест CallbackButton."""
        button = CallbackButton(text="Test", payload="test_payload")
        assert button.text == "Test"
        assert button.payload == "test_payload"
        assert button.type == "callback"

    def test_link_button(self):
        """Тест LinkButton."""
        button = LinkButton(text="Link", url="https://example.com")
        assert button.text == "Link"
        assert button.url == "https://example.com"
        assert button.type == "link"

    def test_chat_button(self):
        """Тест ChatButton."""
        button = ChatButton(text="Chat", chat_title="Test Chat")
        assert button.text == "Chat"
        assert button.chat_title == "Test Chat"
        assert button.type == "chat"

    def test_request_contact_button(self):
        """Тест RequestContactButton."""
        button = RequestContactButton(text="Contact")
        assert button.text == "Contact"
        assert button.type == "request_contact"

    def test_request_geo_location_button(self):
        """Тест RequestGeoLocationButton."""
        button = RequestGeoLocationButton(text="Location")
        assert button.text == "Location"
        assert button.type == "request_geo_location"


class TestBotCommand:
    """Тесты для BotCommand."""

    def test_bot_command_init(self):
        """Тест инициализации BotCommand."""
        command = BotCommand(name="start", description="Start command")
        assert command.name == "start"
        assert command.description == "Start command"

    def test_bot_command_minimal(self):
        """Тест BotCommand с минимальными параметрами."""
        command = BotCommand(name="help")
        assert command.name == "help"


class TestNewMessageLink:
    """Тесты для NewMessageLink."""

    def test_new_message_link_reply(self):
        """Тест NewMessageLink для reply."""
        link = NewMessageLink(type=MessageLinkType.REPLY, mid="msg_123")
        assert link.type == MessageLinkType.REPLY
        assert link.mid == "msg_123"

    def test_new_message_link_forward(self):
        """Тест NewMessageLink для forward."""
        link = NewMessageLink(type=MessageLinkType.FORWARD, mid="msg_456")
        assert link.type == MessageLinkType.FORWARD
        assert link.mid == "msg_456"


class TestInputMedia:
    """Тесты для InputMedia."""

    def test_input_media_init(self):
        """Тест инициализации InputMedia."""
        # InputMedia требует путь к файлу, поэтому используем мок
        # В реальности нужно будет создать временный файл для теста

    def test_input_media_buffer_init(self):
        """Тест инициализации InputMediaBuffer."""
        buffer = InputMediaBuffer(
            buffer=b"fake image data", filename="test.png"
        )
        assert buffer.buffer == b"fake image data"
        assert buffer.filename == "test.png"
        assert buffer.type in [UploadType.IMAGE, UploadType.FILE]


class TestEnums:
    """Тесты для перечислений."""

    def test_attachment_type(self):
        """Тест AttachmentType."""
        assert AttachmentType.IMAGE
        assert AttachmentType.VIDEO
        assert AttachmentType.AUDIO
        assert AttachmentType.FILE
        assert AttachmentType.STICKER
        assert AttachmentType.INLINE_KEYBOARD

    def test_message_link_type(self):
        """Тест MessageLinkType."""
        assert MessageLinkType.REPLY
        assert MessageLinkType.FORWARD

    def test_upload_type(self):
        """Тест UploadType."""
        assert UploadType.IMAGE
        assert UploadType.VIDEO
        assert UploadType.AUDIO
        assert UploadType.FILE


class TestDialogMuted:
    """Тесты для DialogMuted."""

    _USER: ClassVar[dict[str, Any]] = {
        "user_id": 1,
        "first_name": "Bot",
        "is_bot": True,
        "last_activity_time": 0,
    }

    def _make_event(self, muted_until: int):
        from maxapi.types.updates.dialog_muted import DialogMuted

        return DialogMuted(
            timestamp=0,
            chat_id=100,
            muted_until=muted_until,
            user=self._USER,
        )

    def test_muted_until_datetime_forever(self):
        """При муте навсегда (INT64_MAX) возвращает datetime.max."""
        INT64_MAX = 9223372036854775807
        event = self._make_event(INT64_MAX)
        result = event.muted_until_datetime
        assert result == datetime.max

    def test_muted_until_datetime_normal(self):
        """При обычном значении возвращает корректный datetime."""
        # 1 января 2030 года в миллисекундах
        ts_ms = 1893456000000
        event = self._make_event(ts_ms)
        result = event.muted_until_datetime
        assert result is not None
        assert isinstance(result, datetime)
        assert result == datetime.fromtimestamp(ts_ms / 1000)
