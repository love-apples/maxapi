"""Тесты для BaseConnection.upload_file."""

from unittest.mock import Mock, patch

from maxapi.client.default import DefaultConnectionProperties
from maxapi.connection.base import BaseConnection
from maxapi.enums.upload_type import UploadType
from requests import Session


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

    def test_known_extension_uses_guessed_mime(self, tmp_path):
        """Для .png используется результат guess_type."""
        test_file = tmp_path / "photo.png"
        test_file.write_bytes(b"fake-png-data")

        mock_response = Mock()
        mock_response.text = '{"token":"t"}'

        mock_cm = Mock()
        mock_cm.__enter__.return_value = mock_response
        mock_cm.__exit__.return_value = False

        mock_session = Mock(spec=Session)
        mock_session.closed = False
        mock_session.post = Mock(return_value=mock_cm)

        conn, _bot = _make_connection_with_bot(session=mock_session)

        conn.upload_file(
            url="https://upload.example.com",
            path=str(test_file),
            type=UploadType.IMAGE,
        )

        mock_session.post.assert_called_once()

    def test_unknown_extension_falls_back_to_type_wildcard(
        self, tmp_path
    ):
        """Для неизвестного расширения используется фоллбэк type/*."""
        test_file = tmp_path / "data.xyz123unknownext"
        test_file.write_bytes(b"some-data")

        mock_response = Mock()
        mock_response.text = '{"token":"t"}'

        mock_cm = Mock()
        mock_cm.__enter__.return_value = mock_response
        mock_cm.__exit__.return_value = False

        mock_session = Mock(spec=Session)
        mock_session.closed = False
        mock_session.post = Mock(return_value=mock_cm)

        conn, _bot = _make_connection_with_bot(session=mock_session)

        with patch(
            "maxapi.connection.base.mimetypes.guess_type",
            return_value=(None, None),
        ):
            conn.upload_file(
                url="https://upload.example.com",
                path=str(test_file),
                type=UploadType.FILE,
            )

        mock_session.post.assert_called_once()


class TestUploadFileTempSession:
    """Тесты для fallback Session с timeout в upload_file."""

    def test_temp_session_with_timeout_when_no_session(self, tmp_path):
        """Если conn.session is None, _get_session создаёт новую."""
        test_file = tmp_path / "doc.pdf"
        test_file.write_bytes(b"fake-pdf")

        mock_response = Mock()
        mock_response.text = '{"token":"t"}'

        conn, _bot = _make_connection_with_bot(session=None)
        expected_timeout = conn.default_connection.timeout

        mock_cm = Mock()
        mock_cm.__enter__.return_value = mock_response
        mock_cm.__exit__.return_value = False

        mock_temp_session = Mock()
        mock_temp_session.post = Mock(return_value=mock_cm)

        with patch(
            "maxapi.connection.base.Session",
        ) as mock_cs_cls:
            mock_cs_cls.return_value.__enter__ = Mock(
                return_value=mock_temp_session
            )
            mock_cs_cls.return_value.__exit__ = Mock(return_value=False)
            conn.upload_file(
                url="https://upload.example.com",
                path=str(test_file),
                type=UploadType.FILE,
            )

            mock_cs_cls.assert_called_once_with(timeout=expected_timeout)
            mock_temp_session.post.assert_called_once()

    def test_temp_session_with_timeout_when_session_closed(
        self, tmp_path
    ):
        """Если bot.session.closed=True, создаётся временная сессия."""
        test_file = tmp_path / "doc.txt"
        test_file.write_bytes(b"data")

        mock_response = Mock()
        mock_response.text = Mock(return_value='{"token":"t"}')

        closed_session = Mock(spec=Session)
        closed_session.closed = True

        conn, bot = _make_connection_with_bot(session=closed_session)
        expected_timeout = bot.default_connection.timeout

        mock_cm = Mock()
        mock_cm.__enter__.return_value = mock_response
        mock_cm.__exit__.return_value = False

        mock_temp_session = Mock()
        mock_temp_session.post = Mock(return_value=mock_cm)

        with patch(
            "maxapi.connection.base.ClientSession",
        ) as mock_cs_cls:
            mock_cs_cls.return_value.__enter__ = Mock(
                return_value=mock_temp_session
            )
            mock_cs_cls.return_value.__exit__ = Mock(return_value=False)
            conn.upload_file(
                url="https://upload.example.com",
                path=str(test_file),
                type=UploadType.FILE,
            )

            mock_cs_cls.assert_called_once_with(timeout=expected_timeout)

    def test_uses_existing_session_when_open(self, tmp_path):
        """Если conn.session открыта, используется она, а не новая."""
        test_file = tmp_path / "img.jpg"
        test_file.write_bytes(b"jpeg-data")

        mock_response = Mock()
        mock_response.text = '{"token":"t"}'

        mock_cm = Mock()
        mock_cm.__enter__.return_value = mock_response
        mock_cm.__exit__.return_value = False

        mock_session = Mock(spec=Session)
        mock_session.closed = False
        mock_session.post = Mock(return_value=mock_cm)

        conn, _bot = _make_connection_with_bot(session=mock_session)

        with patch(
            "maxapi.connection.base.Session",
        ) as mock_cs_cls:
            conn.upload_file(
                url="https://upload.example.com",
                path=str(test_file),
                type=UploadType.IMAGE,
            )

            mock_cs_cls.assert_not_called()
            mock_session.post.assert_called_once()
