"""Тесты для лимитов загрузки медиафайлов (POST /uploads)."""

import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import ClientSession
from maxapi.client.default import DefaultConnectionProperties
from maxapi.connection.base import BaseConnection
from maxapi.enums.upload_type import UploadType
from maxapi.utils.upload_limits import (
    GB,
    MB,
    UPLOAD_LIMITS,
    UploadLimits,
    check_upload_size,
)

IMAGE_LIMIT = UPLOAD_LIMITS[UploadType.IMAGE].max_size

TINY_LIMIT = 16
TINY_LIMITS = {UploadType.IMAGE: UploadLimits(formats=(), max_size=TINY_LIMIT)}


def _make_connection_with_bot(*, session=None):
    """Создаёт BaseConnection с замоканным ботом."""
    conn = BaseConnection()
    bot = Mock()
    bot.default_connection = DefaultConnectionProperties()
    bot.session = session
    conn.bot = bot
    return conn, bot


def _make_mock_session():
    """Создаёт замоканную aiohttp-сессию для upload-запросов."""
    mock_response = AsyncMock()
    mock_response.text = AsyncMock(return_value='{"token":"t"}')

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_response
    mock_cm.__aexit__.return_value = False

    mock_session = AsyncMock(spec=ClientSession)
    mock_session.closed = False
    mock_session.post = Mock(return_value=mock_cm)
    return mock_session


class TestUploadLimitsValues:
    """Значения UPLOAD_LIMITS соответствуют документации MAX."""

    def test_all_upload_types_are_covered(self):
        """Лимиты заданы для каждого UploadType."""
        assert set(UPLOAD_LIMITS) == set(UploadType)

    @pytest.mark.parametrize(
        ("type", "expected"),
        [
            (
                UploadType.IMAGE,
                UploadLimits(
                    formats=(
                        "JPG",
                        "JPEG",
                        "PNG",
                        "GIF",
                        "TIFF",
                        "BMP",
                        "HEIC",
                    ),
                    max_size=50 * MB,
                    max_dimensions=(7680, 7680),
                ),
            ),
            (
                UploadType.VIDEO,
                UploadLimits(
                    formats=("MP4", "MOV", "MKV", "WEBM"),
                    max_size=250 * MB,
                ),
            ),
            (
                UploadType.AUDIO,
                UploadLimits(
                    formats=("MP3", "WAV", "M4A"),
                    max_size=256 * MB,
                    max_duration=3600,
                ),
            ),
            (
                UploadType.FILE,
                UploadLimits(
                    formats=("TXT", "DOC", "PDF"),
                    max_size=4 * GB,
                ),
            ),
        ],
    )
    def test_limits_match_documentation(self, type, expected):
        """Лимиты каждого типа совпадают с таблицей из документации."""
        assert UPLOAD_LIMITS[type] == expected

    def test_limits_are_frozen(self):
        """UploadLimits неизменяем."""
        with pytest.raises(AttributeError):
            UPLOAD_LIMITS[UploadType.IMAGE].max_size = 1


class TestCheckUploadSize:
    """Тесты для check_upload_size."""

    @pytest.mark.parametrize("type", list(UploadType))
    def test_size_equal_to_limit_is_allowed(self, type):
        """Размер, равный лимиту, считается допустимым."""
        assert check_upload_size(UPLOAD_LIMITS[type].max_size, type) is True

    @pytest.mark.parametrize("type", list(UploadType))
    def test_size_above_limit_is_rejected(self, type):
        """Размер на байт больше лимита считается превышением."""
        size = UPLOAD_LIMITS[type].max_size + 1
        assert check_upload_size(size, type) is False

    def test_zero_size_is_allowed(self):
        """Пустой файл проходит проверку."""
        assert check_upload_size(0, UploadType.IMAGE) is True

    def test_no_warning_when_within_limit(self, caplog):
        """Для файла в пределах лимита предупреждений нет."""
        with caplog.at_level(logging.WARNING, logger="bot"):
            check_upload_size(IMAGE_LIMIT, UploadType.IMAGE)

        assert caplog.records == []

    def test_warning_contains_type_and_sizes(self, caplog):
        """Предупреждение содержит тип, фактический размер и лимит."""
        with caplog.at_level(logging.WARNING, logger="bot"):
            result = check_upload_size(100 * MB, UploadType.IMAGE)

        assert result is False
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.name == "bot"
        assert record.levelno == logging.WARNING
        message = record.getMessage()
        assert "image" in message
        assert "100.0 МБ" in message
        assert "50.0 МБ" in message

    def test_string_type_is_accepted(self, caplog):
        """Строковый тип нормализуется в UploadType."""
        with caplog.at_level(logging.WARNING, logger="bot"):
            result = check_upload_size(100 * MB, "image")

        assert result is False
        assert len(caplog.records) == 1
        assert "image" in caplog.records[0].getMessage()

    def test_unknown_type_is_allowed_without_warning(self, caplog):
        """Неизвестный тип считается допустимым: решает сервер."""
        with caplog.at_level(logging.WARNING, logger="bot"):
            result = check_upload_size(1, "unknown")

        assert result is True
        assert caplog.records == []

    def test_warning_contains_exact_bytes(self, caplog):
        """Байты в тексте различают размеры, округляемые одинаково."""
        size = IMAGE_LIMIT + 1

        with caplog.at_level(logging.WARNING, logger="bot"):
            check_upload_size(size, UploadType.IMAGE)

        message = caplog.records[0].getMessage()
        assert f"{size} байт" in message
        assert f"{IMAGE_LIMIT} байт" in message
        assert "50.0 МБ > 50.0 МБ" not in message

    def test_warning_contains_file_name(self, caplog):
        """Имя файла попадает в предупреждение, если передано."""
        with caplog.at_level(logging.WARNING, logger="bot"):
            check_upload_size(
                100 * MB,
                UploadType.IMAGE,
                name="photo.png",
            )

        assert "photo.png" in caplog.records[0].getMessage()

    def test_warning_for_file_type_uses_gigabytes(self, caplog):
        """Лимит для file показывается в гигабайтах."""
        with caplog.at_level(logging.WARNING, logger="bot"):
            check_upload_size(5 * GB, UploadType.FILE)

        message = caplog.records[0].getMessage()
        assert "5.0 ГБ" in message
        assert "4.0 ГБ" in message


class TestUploadFileSizeCheck:
    """Мягкая проверка размера в BaseConnection.upload_file."""

    async def _upload(self, path):
        """Загружает файл через замоканную сессию."""
        mock_session = _make_mock_session()
        conn, _bot = _make_connection_with_bot(session=mock_session)

        result = await conn.upload_file(
            url="https://upload.example.com",
            path=str(path),
            type=UploadType.IMAGE,
        )

        mock_session.post.assert_called_once()
        return result

    async def test_warns_for_too_big_file(self, caplog, tmp_path):
        """Файл больше лимита вызывает предупреждение с именем файла."""
        file_path = tmp_path / "big.png"
        file_path.write_bytes(b"\x00" * (TINY_LIMIT + 1))

        with (
            patch.dict(
                "maxapi.utils.upload_limits.UPLOAD_LIMITS",
                TINY_LIMITS,
            ),
            caplog.at_level(logging.WARNING, logger="bot"),
        ):
            result = await self._upload(file_path)

        assert result == '{"token":"t"}'
        assert len(caplog.records) == 1
        assert "big.png" in caplog.records[0].getMessage()

    async def test_no_warning_for_small_file(self, caplog, tmp_path):
        """Файл в пределах лимита не вызывает предупреждений."""
        file_path = tmp_path / "small.png"
        file_path.write_bytes(b"\x00" * TINY_LIMIT)

        with (
            patch.dict(
                "maxapi.utils.upload_limits.UPLOAD_LIMITS",
                TINY_LIMITS,
            ),
            caplog.at_level(logging.WARNING, logger="bot"),
        ):
            result = await self._upload(file_path)

        assert result == '{"token":"t"}'
        assert caplog.records == []

    async def test_real_file_size_is_read_from_fs(self, caplog, tmp_path):
        """Размер берётся из реального файла, а не из аргументов."""
        file_path = tmp_path / "sparse.png"
        with file_path.open("wb") as f:
            f.truncate(TINY_LIMIT + 1)

        with (
            patch.dict(
                "maxapi.utils.upload_limits.UPLOAD_LIMITS",
                TINY_LIMITS,
            ),
            caplog.at_level(logging.WARNING, logger="bot"),
        ):
            await self._upload(file_path)

        message = caplog.records[0].getMessage()
        assert f"{TINY_LIMIT + 1} байт" in message


class TestUploadFileBufferSizeCheck:
    """Мягкая проверка размера в BaseConnection.upload_file_buffer."""

    async def _upload(self, buffer, filename):
        """Загружает буфер через замоканную сессию."""
        mock_session = _make_mock_session()
        conn, _bot = _make_connection_with_bot(session=mock_session)

        result = await conn.upload_file_buffer(
            filename=filename,
            url="https://upload.example.com",
            buffer=buffer,
            type=UploadType.IMAGE,
        )

        mock_session.post.assert_called_once()
        return result

    async def test_warns_for_too_big_buffer(self, caplog):
        """Слишком большой буфер вызывает предупреждение с именем файла."""
        with (
            patch.dict(
                "maxapi.utils.upload_limits.UPLOAD_LIMITS",
                TINY_LIMITS,
            ),
            caplog.at_level(logging.WARNING, logger="bot"),
        ):
            result = await self._upload(
                b"\x00" * (TINY_LIMIT + 1),
                "big.png",
            )

        assert result == '{"token":"t"}'
        assert len(caplog.records) == 1
        assert "big.png" in caplog.records[0].getMessage()

    async def test_no_warning_for_small_buffer(self, caplog):
        """Маленький буфер не вызывает предупреждений."""
        with (
            patch.dict(
                "maxapi.utils.upload_limits.UPLOAD_LIMITS",
                TINY_LIMITS,
            ),
            caplog.at_level(logging.WARNING, logger="bot"),
        ):
            result = await self._upload(b"\x00" * TINY_LIMIT, "small.png")

        assert result == '{"token":"t"}'
        assert caplog.records == []
