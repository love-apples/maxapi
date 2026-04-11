from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from maxapi.enums.upload_type import UploadType
from maxapi.exceptions.max import MaxUploadFileFailed
from maxapi.types.input_media import InputMediaBuffer
from maxapi.utils.message import (
    _extract_upload_token_from_response,
    process_input_media,
)


class TestExtractUploadTokenFromResponse:
    def test_extract_file_token(self):
        token = _extract_upload_token_from_response(
            upload_type=UploadType.FILE,
            upload_file_response='{"token":"file-token"}',
        )

        assert token == "file-token"

    def test_extract_image_token(self):
        token = _extract_upload_token_from_response(
            upload_type=UploadType.IMAGE,
            upload_file_response=(
                '{"photos":{"640x480":{"token":"image-token"}}}'
            ),
        )

        assert token == "image-token"

    def test_extract_file_token_raises_on_missing_token(self):
        with pytest.raises(
            MaxUploadFileFailed,
            match="отсутствует token",
        ):
            _extract_upload_token_from_response(
                upload_type=UploadType.FILE,
                upload_file_response='{"ok":true}',
            )

    def test_extract_token_raises_on_invalid_json(self):
        with pytest.raises(
            MaxUploadFileFailed,
            match="Не удалось распарсить ответ",
        ):
            _extract_upload_token_from_response(
                upload_type=UploadType.FILE,
                upload_file_response="not-json",
            )


class TestProcessInputMedia:
    @pytest.mark.anyio
    async def test_process_input_media_for_file_buffer(self):
        base_connection = Mock()
        base_connection.upload_file_buffer = AsyncMock(
            return_value='{"token":"buffer-file-token"}'
        )

        bot = Mock()
        bot.get_upload_url = AsyncMock(
            return_value=SimpleNamespace(
                url="https://upload.local",
                token=None,
            )
        )
        bot.session = None

        media = InputMediaBuffer(
            buffer=b"test-data",
            filename="data.bin",
            type=UploadType.FILE,
        )

        uploaded = await process_input_media(
            base_connection=base_connection,
            bot=bot,
            att=media,
        )

        assert uploaded.type == UploadType.FILE
        assert uploaded.payload.token == "buffer-file-token"
        bot.get_upload_url.assert_awaited_once_with(UploadType.FILE)
        base_connection.upload_file_buffer.assert_awaited_once()

    @pytest.mark.anyio
    async def test_process_input_media_video_raises_without_upload_token(self):
        base_connection = Mock()
        base_connection.upload_file_buffer = AsyncMock(
            return_value='{"ignored":"for-video"}'
        )

        bot = Mock()
        bot.get_upload_url = AsyncMock(
            return_value=SimpleNamespace(
                url="https://upload.local",
                token=None,
            )
        )
        media = InputMediaBuffer(
            buffer=b"video-bytes",
            filename="video.mp4",
            type=UploadType.VIDEO,
        )

        with pytest.raises(
            MaxUploadFileFailed,
            match="token не был получен",
        ):
            await process_input_media(
                base_connection=base_connection,
                bot=bot,
                att=media,
            )
