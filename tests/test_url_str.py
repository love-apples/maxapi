from unittest.mock import AsyncMock, patch

import pytest
from maxapi.types.attachments.attachment import OtherAttachmentPayload
from maxapi.types.attachments.url_str import UrlStr
from url_media_probe import MediaInfo


class TestUrlStrGetInfo:
    """Тесты для UrlStr.get_info()."""

    async def test_delegates_to_media_probe(self):
        """get_info создаёт MediaProbe и вызывает from_url."""
        expected = MediaInfo(
            url="https://example.com/img.jpg",
            mime_type="image/jpeg",
            file_name="img.jpg",
            file_size=12345,
            status="ok",
        )

        with patch("maxapi.types.attachments.url_str.MediaProbe") as MockMP:
            mock_media_probe = AsyncMock()
            MockMP.return_value = mock_media_probe
            mock_media_probe.from_url.return_value = expected

            info = await UrlStr("https://example.com/img.jpg").get_info()

        assert info is expected
        MockMP.assert_called_once_with(raise_on_network=False)
        mock_media_probe.from_url.assert_awaited_once_with(
            "https://example.com/img.jpg",
            timeout=30,
            max_total=256000,
            max_retries=3,
        )

    async def test_get_info_returns_media_info(self):
        """get_info возвращает то, что вернул from_url."""
        expected = MediaInfo(
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

        with patch("maxapi.types.attachments.url_str.MediaProbe") as MockMP:
            mock_media_probe = AsyncMock()
            MockMP.return_value = mock_media_probe
            mock_media_probe.from_url.return_value = expected

            info = await UrlStr("https://example.com/video.mp4").get_info()

        assert info.url == expected.url
        assert info.mime_type == expected.mime_type
        assert info.file_name == expected.file_name
        assert info.width == expected.width
        assert info.height == expected.height
        MockMP.assert_called_once_with(raise_on_network=False)

    async def test_from_attachment_field(self):
        """get_info работает при вызове через поле модели-аттача."""
        expected = MediaInfo(
            url="https://example.com/file.bin",
            mime_type="application/octet-stream",
            file_name="file.bin",
            file_size=999,
            status="ok",
        )

        with patch("maxapi.types.attachments.url_str.MediaProbe") as MockMP:
            mock_media_probe = AsyncMock()
            MockMP.return_value = mock_media_probe
            mock_media_probe.from_url.return_value = expected

            payload = OtherAttachmentPayload(
                url="https://example.com/file.bin"
            )
            assert isinstance(payload.url, UrlStr)
            info = await payload.url.get_info()

        assert info is expected
        MockMP.assert_called_once_with(raise_on_network=False)
        mock_media_probe.from_url.assert_awaited_once_with(
            "https://example.com/file.bin",
            timeout=30,
            max_total=256000,
            max_retries=3,
        )

    async def test_returns_error_for_unreachable_url(self):
        """get_info возвращает MediaInfo(status='error') при сетевой ошибке."""
        error_info = MediaInfo(
            url="https://example.com/bad",
            mime_type="",
            file_name="",
            file_size=None,
            status="error",
            parse_note="Сетевая ошибка",
        )

        with patch("maxapi.types.attachments.url_str.MediaProbe") as MockMP:
            mock_media_probe = AsyncMock()
            MockMP.return_value = mock_media_probe
            mock_media_probe.from_url.return_value = error_info

            info = await UrlStr("https://example.com/bad").get_info()

        assert info.status == "error"
        assert info.parse_note == "Сетевая ошибка"

    async def test_raises_on_network_error(self):
        """При raise_on_network_error=True MediaProbe пробрасывает ошибку."""
        import aiohttp

        with patch("maxapi.types.attachments.url_str.MediaProbe") as MockMP:
            mock_media_probe = AsyncMock()
            MockMP.return_value = mock_media_probe
            mock_media_probe.from_url.side_effect = aiohttp.ClientError(
                "Connection error"
            )

            with pytest.raises(aiohttp.ClientError):
                await UrlStr("https://example.com/bad").get_info(
                    raise_on_network_error=True
                )

        MockMP.assert_called_once_with(raise_on_network=True)

    async def test_returns_error_by_default(self):
        """По умолчанию сетевая ошибка возвращает MediaInfo(status='error')."""
        error_info = MediaInfo(
            url="https://example.com/bad",
            mime_type="",
            file_name="",
            file_size=None,
            status="error",
            parse_note="Сетевая ошибка",
        )

        with patch("maxapi.types.attachments.url_str.MediaProbe") as MockMP:
            mock_media_probe = AsyncMock()
            MockMP.return_value = mock_media_probe
            mock_media_probe.from_url.return_value = error_info

            info = await UrlStr("https://example.com/bad").get_info()

        assert info.status == "error"
        assert info.parse_note == "Сетевая ошибка"
        MockMP.assert_called_once_with(raise_on_network=False)

    async def test_download_file_without_get_info(self):
        """download_file без get_info сам выполняет пробу по заголовкам."""
        from pathlib import Path

        saved = Path("downloads") / "file.bin"

        with patch("maxapi.types.attachments.url_str.MediaProbe") as MockMP:
            mock_media_probe = AsyncMock()
            MockMP.return_value = mock_media_probe
            mock_media_probe.from_url.return_value = MediaInfo(
                url="https://example.com/file.bin",
                mime_type="application/octet-stream",
                file_name="file.bin",
                file_size=999,
                status="ok",
            )
            mock_media_probe.full_file_save.return_value = saved

            url = UrlStr("https://example.com/file.bin")
            result = await url.download_file(Path("downloads"))

        assert result == saved
        assert url.media_probe is mock_media_probe
        MockMP.assert_called_once_with(raise_on_network=True)
        mock_media_probe.from_url.assert_awaited_once_with(
            "https://example.com/file.bin",
            timeout=30,
            max_total=0,
            max_retries=3,
        )
        mock_media_probe.full_file_save.assert_awaited_once_with(
            Path("downloads"), file_name=None
        )

    async def test_download_file_raises_on_network_error(self):
        """download_file оборачивает сетевую ошибку в DownloadFileError."""
        from pathlib import Path

        import aiohttp
        from maxapi.exceptions.download_file import DownloadFileError

        with patch("maxapi.types.attachments.url_str.MediaProbe") as MockMP:
            mock_media_probe = AsyncMock()
            MockMP.return_value = mock_media_probe
            mock_media_probe.from_url.side_effect = aiohttp.ClientError(
                "Connection error"
            )

            with pytest.raises(DownloadFileError) as exc_info:
                await UrlStr("https://example.com/bad").download_file(
                    Path("downloads")
                )

        assert isinstance(exc_info.value.__cause__, aiohttp.ClientError)
        MockMP.assert_called_once_with(raise_on_network=True)

    async def test_download_file_reuses_existing_probe(self):
        """download_file после get_info не выполняет повторную пробу."""
        from pathlib import Path

        saved = Path("downloads") / "img.jpg"

        with patch("maxapi.types.attachments.url_str.MediaProbe") as MockMP:
            mock_media_probe = AsyncMock()
            MockMP.return_value = mock_media_probe
            mock_media_probe.full_file_save.return_value = saved

            url = UrlStr("https://example.com/img.jpg")
            url.media_probe = mock_media_probe
            result = await url.download_file(Path("downloads"))

        assert result == saved
        mock_media_probe.from_url.assert_not_awaited()
        mock_media_probe.full_file_save.assert_awaited_once_with(
            Path("downloads"), file_name=None
        )
