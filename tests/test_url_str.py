from unittest.mock import AsyncMock, patch

from maxapi.types.attachments.attachment import OtherAttachmentPayload
from maxapi.types.attachments.url_str import UrlStr
from maxapi.types.file_info import FileInfo


class TestUrlStrGetInfo:
    """Тесты для UrlStr.get_info()."""

    async def test_delegates_to_file_inspector(self):
        """get_info создаёт FileInspector и вызывает inspect_url."""
        expected = FileInfo(
            url="https://example.com/img.jpg",
            mime_type="image/jpeg",
            file_name="img.jpg",
            file_size=12345,
            status="ok",
        )

        with patch("maxapi.types.attachments.url_str.FileInspector") as MockFI:
            mock_inspector = AsyncMock()
            MockFI.return_value = mock_inspector
            mock_inspector.inspect_url.return_value = expected

            info = await UrlStr("https://example.com/img.jpg").get_info()

        assert info is expected
        mock_inspector.inspect_url.assert_awaited_once_with(
            "https://example.com/img.jpg"
        )

    async def test_returns_file_info_from_inspect_url(self):
        """get_info возвращает то, что вернул inspect_url."""
        expected = FileInfo(
            url="https://example.com/video.mp4",
            mime_type="video/mp4",
            file_name="video.mp4",
            file_size=50_000_000,
            width=1920,
            height=1080,
            duration=120.0,
            fps=24.0,
            format="MP4",
            status="ok",
        )

        with patch("maxapi.types.attachments.url_str.FileInspector") as MockFI:
            mock_inspector = AsyncMock()
            MockFI.return_value = mock_inspector
            mock_inspector.inspect_url.return_value = expected

            info = await UrlStr("https://example.com/video.mp4").get_info()

        assert info.url == expected.url
        assert info.mime_type == expected.mime_type
        assert info.file_name == expected.file_name
        assert info.width == expected.width
        assert info.height == expected.height

    async def test_from_attachment_field(self):
        """get_info работает при вызове через поле модели-аттача."""
        expected = FileInfo(
            url="https://example.com/file.bin",
            mime_type="application/octet-stream",
            file_name="file.bin",
            file_size=999,
            status="ok",
        )

        with patch("maxapi.types.attachments.url_str.FileInspector") as MockFI:
            mock_inspector = AsyncMock()
            MockFI.return_value = mock_inspector
            mock_inspector.inspect_url.return_value = expected

            payload = OtherAttachmentPayload(url="https://example.com/file.bin")
            info = await payload.url.get_info()

        assert info is expected
        mock_inspector.inspect_url.assert_awaited_once_with(
            "https://example.com/file.bin"
        )

    async def test_returns_error_for_unreachable_url(self):
        """get_info возвращает FileInfo(status='error') при сетевой ошибке."""
        error_info = FileInfo(
            url="https://example.com/bad",
            mime_type="",
            file_name="",
            file_size=None,
            status="error",
            parse_note="Сетевая ошибка",
        )

        with patch("maxapi.types.attachments.url_str.FileInspector") as MockFI:
            mock_inspector = AsyncMock()
            MockFI.return_value = mock_inspector
            mock_inspector.inspect_url.return_value = error_info

            info = await UrlStr("https://example.com/bad").get_info()

        assert info.status == "error"
        assert info.parse_note == "Сетевая ошибка"
