"""Тесты для BaseConnection.upload_file."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import ClientSession
from maxapi.client.default import DefaultConnectionProperties
from maxapi.connection.base import BaseConnection
from maxapi.enums.upload_type import UploadType


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

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response

        mock_session = AsyncMock(spec=ClientSession)
        mock_session.closed = False
        mock_session.post = Mock(return_value=mock_cm)

        conn, _bot = _make_connection_with_bot(session=mock_session)

        await conn.upload_file(
            url="https://upload.example.com",
            path=str(test_file),
            type=UploadType.IMAGE,
        )

        mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_extension_falls_back_to_type_wildcard(
        self, tmp_path
    ):
        """Для неизвестного расширения используется фоллбэк type/*."""
        test_file = tmp_path / "data.xyz123unknownext"
        test_file.write_bytes(b"some-data")

        mock_response = AsyncMock()
        mock_response.text = AsyncMock(return_value='{"token":"t"}')

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response

        mock_session = AsyncMock(spec=ClientSession)
        mock_session.closed = False
        mock_session.post = Mock(return_value=mock_cm)

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

        mock_session.post.assert_called_once()


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

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response

        mock_temp_session = AsyncMock()
        mock_temp_session.post = Mock(return_value=mock_cm)

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
            mock_temp_session.post.assert_called_once()

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

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response

        mock_temp_session = AsyncMock()
        mock_temp_session.post = Mock(return_value=mock_cm)

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

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response

        mock_session = AsyncMock(spec=ClientSession)
        mock_session.closed = False
        mock_session.post = Mock(return_value=mock_cm)

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
            mock_session.post.assert_called_once()
