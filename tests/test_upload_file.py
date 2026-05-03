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

        mock_session = Mock(spec=Session)
        mock_session.closed = False
        mock_session.post = Mock(return_value=mock_response)

        conn, _bot = _make_connection_with_bot(session=mock_session)
        conn.session = mock_session

        conn.upload_file(
            url="https://upload.example.com",
            path=str(test_file),
            type=UploadType.IMAGE,
        )

        mock_session.post.assert_called_once()

    def test_unknown_extension_falls_back_to_type_wildcard(self, tmp_path):
        """Для неизвестного расширения используется фоллбэк type/*."""
        test_file = tmp_path / "data.xyz123unknownext"
        test_file.write_bytes(b"some-data")

        mock_response = Mock()
        mock_response.text = '{"token":"t"}'

        mock_session = Mock(spec=Session)
        mock_session.closed = False
        mock_session.post = Mock(return_value=mock_response)

        conn, _bot = _make_connection_with_bot(session=mock_session)
        conn.session = mock_session

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
        conn.session = None

        mock_temp_session = Mock()
        mock_temp_session.post = Mock(return_value=mock_response)

        with patch(
            "maxapi.connection.base.Session",
            return_value=mock_temp_session,
        ):
            conn.upload_file(
                url="https://upload.example.com",
                path=str(test_file),
                type=UploadType.FILE,
            )

            mock_temp_session.post.assert_called_once()

    def test_temp_session_with_timeout_when_session_closed(self, tmp_path):
        """Если bot.session.closed=True, создаётся временная сессия."""
        test_file = tmp_path / "doc.txt"
        test_file.write_bytes(b"data")

        mock_response = Mock()
        mock_response.text = Mock(return_value='{"token":"t"}')

        closed_session = Mock(spec=Session)
        closed_session.closed = True

        conn, _bot = _make_connection_with_bot(session=closed_session)

        mock_temp_session = Mock()
        mock_temp_session.post = Mock(return_value=mock_response)

        with patch(
            "maxapi.connection.base.Session", return_value=mock_temp_session
        ) as mock_cs_cls:
            conn.upload_file(
                url="https://upload.example.com",
                path=str(test_file),
                type=UploadType.FILE,
            )

            mock_cs_cls.assert_called_once()

    def test_uses_existing_session_when_open(self, tmp_path):
        """Если conn.session открыта, используется она, а не новая."""
        test_file = tmp_path / "img.jpg"
        test_file.write_bytes(b"jpeg-data")

        mock_response = Mock()
        mock_response.text = '{"token":"t"}'

        mock_session = Mock(spec=Session)
        mock_session.closed = False
        mock_session.post = Mock(return_value=mock_response)

        conn, _bot = _make_connection_with_bot(session=mock_session)
        conn.session = mock_session

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
