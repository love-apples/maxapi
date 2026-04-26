"""Тесты для BaseConnection.upload_file."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import ClientSession
from maxapi.client.default import DefaultConnectionProperties
from maxapi.connection.base import BaseConnection
from maxapi.enums.upload_type import UploadType
from maxapi.types.input_media import InputMedia, InputMediaBuffer


def _make_connection_with_bot(*, session=None):
    """Создаёт BaseConnection с замоканным ботом."""
    conn = BaseConnection()
    bot = Mock()
    bot.default_connection = DefaultConnectionProperties()
    bot.session = session
    conn.bot = bot
    return conn, bot


class TestUploadFileMimetypesFallback:
    """Тесты для mimetypes.guess_type() фоллбэка в upload_file."""

    @pytest.mark.asyncio
    async def test_known_extension_uses_guessed_mime(self, tmp_path):
        """Для .png используется результат guess_type."""
        test_file = tmp_path / "photo.png"
        test_file.write_bytes(b"fake-png-data")

        mock_response = AsyncMock()
        mock_response.text = AsyncMock(return_value='{"token":"t"}')

        mock_session = AsyncMock(spec=ClientSession)
        mock_session.closed = False
        mock_session.post = AsyncMock(return_value=mock_response)

        conn, _bot = _make_connection_with_bot(session=mock_session)

        await conn.upload_file(
            url="https://upload.example.com",
            path=str(test_file),
            type=UploadType.IMAGE,
        )

        mock_session.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_extension_falls_back_to_type_wildcard(
        self, tmp_path
    ):
        """Для неизвестного расширения используется фоллбэк type/*."""
        test_file = tmp_path / "data.xyz123unknownext"
        test_file.write_bytes(b"some-data")

        mock_response = AsyncMock()
        mock_response.text = AsyncMock(return_value='{"token":"t"}')

        mock_session = AsyncMock(spec=ClientSession)
        mock_session.closed = False
        mock_session.post = AsyncMock(return_value=mock_response)

        conn, _bot = _make_connection_with_bot(session=mock_session)

        with patch(
            "maxapi.connection.base.mimetypes.guess_type",
            return_value=(None, None),
        ):
            await conn.upload_file(
                url="https://upload.example.com",
                path=str(test_file),
                type=UploadType.FILE,
            )

        mock_session.post.assert_awaited_once()


class TestUploadFileTempSession:
    """Тесты для fallback ClientSession с timeout в upload_file."""

    @pytest.mark.asyncio
    async def test_temp_session_with_timeout_when_no_session(self, tmp_path):
        """Если bot.session is None, создаётся временная сессия с timeout."""
        test_file = tmp_path / "doc.pdf"
        test_file.write_bytes(b"fake-pdf")

        mock_response = AsyncMock()
        mock_response.text = AsyncMock(return_value='{"token":"t"}')

        conn, bot = _make_connection_with_bot(session=None)
        expected_timeout = bot.default_connection.timeout

        mock_temp_session = AsyncMock()
        mock_temp_session.post = AsyncMock(return_value=mock_response)

        with patch(
            "maxapi.connection.base.ClientSession",
        ) as mock_cs_cls:
            mock_cs_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_temp_session
            )
            mock_cs_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await conn.upload_file(
                url="https://upload.example.com",
                path=str(test_file),
                type=UploadType.FILE,
            )

            mock_cs_cls.assert_called_once_with(timeout=expected_timeout)
            mock_temp_session.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_temp_session_with_timeout_when_session_closed(
        self, tmp_path
    ):
        """Если bot.session.closed=True, создаётся временная сессия."""
        test_file = tmp_path / "doc.txt"
        test_file.write_bytes(b"data")

        mock_response = AsyncMock()
        mock_response.text = AsyncMock(return_value='{"token":"t"}')

        closed_session = Mock(spec=ClientSession)
        closed_session.closed = True

        conn, bot = _make_connection_with_bot(session=closed_session)
        expected_timeout = bot.default_connection.timeout

        mock_temp_session = AsyncMock()
        mock_temp_session.post = AsyncMock(return_value=mock_response)

        with patch(
            "maxapi.connection.base.ClientSession",
        ) as mock_cs_cls:
            mock_cs_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_temp_session
            )
            mock_cs_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            await conn.upload_file(
                url="https://upload.example.com",
                path=str(test_file),
                type=UploadType.FILE,
            )

            mock_cs_cls.assert_called_once_with(timeout=expected_timeout)

    @pytest.mark.asyncio
    async def test_uses_existing_session_when_open(self, tmp_path):
        """Если bot.session открыта, используется она, а не temp."""
        test_file = tmp_path / "img.jpg"
        test_file.write_bytes(b"jpeg-data")

        mock_response = AsyncMock()
        mock_response.text = AsyncMock(return_value='{"token":"t"}')

        mock_session = AsyncMock(spec=ClientSession)
        mock_session.closed = False
        mock_session.post = AsyncMock(return_value=mock_response)

        conn, _bot = _make_connection_with_bot(session=mock_session)

        with patch(
            "maxapi.connection.base.ClientSession",
        ) as mock_cs_cls:
            await conn.upload_file(
                url="https://upload.example.com",
                path=str(test_file),
                type=UploadType.IMAGE,
            )

            mock_cs_cls.assert_not_called()
            mock_session.post.assert_awaited_once()


def assert_invalid_type_error(exc_info, invalid_value: str) -> None:
    """Проверяет текст ошибки для невалидного type."""
    message = str(exc_info.value)
    assert "Неверный тип загружаемого файла" in message
    assert repr(invalid_value) in message
    assert "file" in message
    assert "image" in message
    assert "video" in message
    assert "audio" in message


class TestInputMediaTypeValidation:
    """Тесты валидации type в InputMedia."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("file", UploadType.FILE),
            ("image", UploadType.IMAGE),
            ("video", UploadType.VIDEO),
            ("audio", UploadType.AUDIO),
        ],
    )
    def test_accepts_valid_string_type(
        self, tmp_path, monkeypatch, value, expected
    ):
        """Явно переданный строковый type валидируется без autodetect."""
        test_file = tmp_path / "sample.bin"
        test_file.write_bytes(b"fake-data")

        mock_detect = Mock(return_value=UploadType.FILE)
        monkeypatch.setattr(
            "maxapi.types.input_media.detect_file_type",
            mock_detect,
        )

        media = InputMedia(path=str(test_file), type=value)

        assert media.path == str(test_file)
        assert media.type == expected
        mock_detect.assert_not_called()

    def test_invalid_string_type_raises_value_error(self, tmp_path):
        """Невалидный строковый type вызывает ValueError со списком значений."""  # noqa: E501
        test_file = tmp_path / "sample.bin"
        test_file.write_bytes(b"fake-data")

        with pytest.raises(ValueError) as exc_info:  # noqa: PT011
            InputMedia(path=str(test_file), type="document")

        assert_invalid_type_error(exc_info, "document")

    def test_none_type_detects_from_file(self, tmp_path, monkeypatch):
        """Если type не передан, тип определяется автоматически."""
        test_file = tmp_path / "sample.bin"
        test_file.write_bytes(b"fake-data")

        mock_detect = Mock(return_value=UploadType.VIDEO)
        monkeypatch.setattr(
            "maxapi.types.input_media.detect_file_type",
            mock_detect,
        )

        media = InputMedia(path=str(test_file))

        assert media.path == str(test_file)
        assert media.type == UploadType.VIDEO
        mock_detect.assert_called_once()

    def test_accepts_enum_type_without_autodetect(self, tmp_path, monkeypatch):
        """Явно переданный UploadType используется без autodetect."""
        test_file = tmp_path / "sample.bin"
        test_file.write_bytes(b"fake-data")

        mock_detect = Mock(return_value=UploadType.FILE)
        monkeypatch.setattr(
            "maxapi.types.input_media.detect_file_type",
            mock_detect,
        )

        media = InputMedia(path=str(test_file), type=UploadType.IMAGE)

        assert media.type == UploadType.IMAGE
        mock_detect.assert_not_called()


class TestInputMediaBufferTypeValidation:
    """Тесты валидации type в InputMediaBuffer."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("file", UploadType.FILE),
            ("image", UploadType.IMAGE),
            ("video", UploadType.VIDEO),
            ("audio", UploadType.AUDIO),
        ],
    )
    def test_accepts_valid_string_type(self, monkeypatch, value, expected):
        """Явно переданный строковый type валидируется без autodetect."""
        mock_detect = Mock(return_value=UploadType.FILE)
        monkeypatch.setattr(
            "maxapi.types.input_media.detect_file_type",
            mock_detect,
        )

        media = InputMediaBuffer(
            buffer=b"fake-bytes",
            filename="sample.bin",
            type=value,
        )

        assert media.filename == "sample.bin"
        assert media.buffer == b"fake-bytes"
        assert media.type == expected
        mock_detect.assert_not_called()

    def test_invalid_string_type_raises_value_error(self):
        """Невалидный строковый type вызывает ValueError со списком значений."""  # noqa: E501
        with pytest.raises(ValueError) as exc_info:  # noqa: PT011
            InputMediaBuffer(
                buffer=b"fake-bytes",
                filename="sample.bin",
                type="document",
            )

        assert_invalid_type_error(exc_info, "document")

    def test_none_type_detects_from_buffer(self, monkeypatch):
        """Если type не передан, тип определяется автоматически."""
        mock_detect = Mock(return_value=UploadType.IMAGE)
        monkeypatch.setattr(
            "maxapi.types.input_media.detect_file_type",
            mock_detect,
        )

        media = InputMediaBuffer(buffer=b"fake-bytes")

        assert media.filename is None
        assert media.buffer == b"fake-bytes"
        assert media.type == UploadType.IMAGE
        mock_detect.assert_called_once_with(b"fake-bytes")

    def test_accepts_enum_type_without_autodetect(self, monkeypatch):
        """Явно переданный UploadType используется без autodetect."""
        mock_detect = Mock(return_value=UploadType.FILE)
        monkeypatch.setattr(
            "maxapi.types.input_media.detect_file_type",
            mock_detect,
        )

        media = InputMediaBuffer(
            buffer=b"fake-bytes",
            filename="sample.bin",
            type=UploadType.AUDIO,
        )

        assert media.type == UploadType.AUDIO
        mock_detect.assert_not_called()

    def test_default_upload_type_input_media_buffer(self, tmp_path):
        """
        Если mimetype не определился (None),
        для файла должен вернуться тип UploadType.FILE
        """
        media = InputMediaBuffer(
            buffer=b"fake-bytes",
            filename="sample.bin",
        )

        assert media.type == UploadType.FILE

    def test_default_upload_type_input_media(self, tmp_path):
        """
        Если mimetype не определился (None),
        для файла должен вернуться тип UploadType.FILE
        """
        test_file = tmp_path / "sample.bin"
        test_file.write_bytes(b"fake-data")

        media = InputMedia(path=test_file)

        assert media.type == UploadType.FILE
