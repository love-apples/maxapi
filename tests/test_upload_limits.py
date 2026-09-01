"""Тесты для лимитов загрузки медиафайлов (POST /uploads)."""

import logging
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from maxapi.enums.upload_type import UploadType
from maxapi.types.input_media import InputMedia, InputMediaBuffer
from maxapi.utils.message import process_input_media
from maxapi.utils.upload_limits import (
    GB,
    MB,
    UPLOAD_LIMITS,
    UploadLimits,
    check_upload_size,
)

IMAGE_LIMIT = 50 * MB


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
            check_upload_size(100 * MB, UploadType.IMAGE)

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.name == "bot"
        assert record.levelno == logging.WARNING
        message = record.getMessage()
        assert "image" in message
        assert "100.0 МБ" in message
        assert "50.0 МБ" in message

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


def _patch_upload_pipeline():
    """Мокает сетевые шаги process_input_media."""
    return (
        patch(
            "maxapi.utils.message._get_upload_info",
            new=AsyncMock(return_value=Mock(url="https://upload", token="t")),
        ),
        patch(
            "maxapi.utils.message._upload_input_media",
            new=AsyncMock(return_value='{"token":"t"}'),
        ),
        patch(
            "maxapi.utils.message._resolve_attachment_token",
            new=AsyncMock(return_value="token-value"),
        ),
    )


class TestProcessInputMediaSizeCheck:
    """Мягкая проверка размера в пайплайне загрузки."""

    async def _run(self, att):
        """Прогоняет process_input_media с замоканной загрузкой."""
        upload_info, upload_media, resolve_token = _patch_upload_pipeline()
        with upload_info, upload_media, resolve_token:
            return await process_input_media(
                base_connection=Mock(),
                bot=Mock(),
                att=att,
            )

    async def test_warns_for_too_big_buffer(self, caplog):
        """Слишком большой InputMediaBuffer вызывает предупреждение."""
        att = InputMediaBuffer(
            buffer=b"\x00" * (IMAGE_LIMIT + 1),
            filename="big.png",
            type=UploadType.IMAGE,
        )

        with caplog.at_level(logging.WARNING, logger="bot"):
            result = await self._run(att)

        assert result.payload.token == "token-value"
        assert len(caplog.records) == 1
        assert "big.png" in caplog.records[0].getMessage()

    async def test_no_warning_for_small_buffer(self, caplog):
        """Маленький InputMediaBuffer не вызывает предупреждений."""
        att = InputMediaBuffer(
            buffer=b"\x00" * 1024,
            filename="small.png",
            type=UploadType.IMAGE,
        )

        with caplog.at_level(logging.WARNING, logger="bot"):
            result = await self._run(att)

        assert result.payload.token == "token-value"
        assert caplog.records == []

    async def test_warns_for_too_big_file(self, caplog, tmp_path):
        """Слишком большой InputMedia вызывает предупреждение."""
        file_path = tmp_path / "big.png"
        file_path.write_bytes(b"\x00" * 16)
        att = InputMedia(path=str(file_path), type=UploadType.IMAGE)

        stat_result = Mock(st_size=IMAGE_LIMIT + 1)
        with (
            patch.object(Path, "stat", return_value=stat_result),
            caplog.at_level(logging.WARNING, logger="bot"),
        ):
            result = await self._run(att)

        assert result.payload.token == "token-value"
        assert len(caplog.records) == 1
        assert "big.png" in caplog.records[0].getMessage()

    async def test_missing_file_does_not_break_pipeline(
        self, caplog, tmp_path
    ):
        """OSError при stat не ломает пайплайн и не логирует warning."""
        file_path = tmp_path / "gone.png"
        file_path.write_bytes(b"\x00" * 16)
        att = InputMedia(path=str(file_path), type=UploadType.IMAGE)
        file_path.unlink()

        with caplog.at_level(logging.WARNING, logger="bot"):
            result = await self._run(att)

        assert result.type == UploadType.IMAGE
        assert result.payload.token == "token-value"
        assert caplog.records == []

    async def test_stat_oserror_is_swallowed(self, caplog, tmp_path):
        """Любая OSError при stat игнорируется проверкой."""
        file_path = tmp_path / "denied.png"
        file_path.write_bytes(b"\x00" * 16)
        att = InputMedia(path=str(file_path), type=UploadType.IMAGE)

        with (
            patch.object(Path, "stat", side_effect=PermissionError),
            caplog.at_level(logging.WARNING, logger="bot"),
        ):
            result = await self._run(att)

        assert result.payload.token == "token-value"
        assert caplog.records == []
