"""
Прямые тесты для модели FileInfo (свойства, __eq__, __str__).
"""

from maxapi.types.file_info import FileInfo


class TestFileInfoProperties:
    """Свойства has_dimensions, is_image, is_audio, is_video."""

    def test_has_dimensions_true(self):
        assert FileInfo(url="u", width=100, height=200).has_dimensions

    def test_has_dimensions_false_none(self):
        assert not FileInfo(url="u").has_dimensions

    def test_is_image_true(self):
        assert FileInfo(url="u", mime_type="image/png").is_image

    def test_is_image_false(self):
        assert not FileInfo(url="u", mime_type="video/mp4").is_image

    def test_is_audio_true(self):
        assert FileInfo(url="u", mime_type="audio/mpeg").is_audio

    def test_is_audio_false(self):
        assert not FileInfo(url="u", mime_type="image/png").is_audio

    def test_is_video_true(self):
        assert FileInfo(url="u", mime_type="video/mp4").is_video

    def test_is_video_false(self):
        assert not FileInfo(url="u", mime_type="audio/mpeg").is_video


class TestFileInfoFileSizeHuman:
    """file_size_human во всех диапазонах."""

    def test_none(self):
        assert FileInfo(url="u").file_size_human == "неизвестно"

    def test_bytes(self):
        assert FileInfo(url="u", file_size=500).file_size_human == "500 байт"

    def test_kb(self):
        assert FileInfo(url="u", file_size=2048).file_size_human == "2 КБ"

    def test_kb_boundary(self):
        assert FileInfo(url="u", file_size=1024).file_size_human == "1 КБ"

    def test_mb(self):
        assert (
            FileInfo(url="u", file_size=1_048_576).file_size_human == "1.0 МБ"
        )

    def test_gb(self):
        assert (
            FileInfo(url="u", file_size=2_147_483_648).file_size_human
            == "2.00 ГБ"
        )


class TestFileInfoEq:
    """__eq__: сравнение без url и file_name."""

    def test_equal_same_content(self):
        a = FileInfo(url="a", file_name="x", mime_type="image/png")
        b = FileInfo(url="b", file_name="y", mime_type="image/png")
        assert a == b

    def test_not_equal_different_content(self):
        a = FileInfo(url="a", mime_type="image/png")
        b = FileInfo(url="b", mime_type="image/jpeg")
        assert a != b

    def test_not_implemented(self):
        assert FileInfo(url="u").__eq__(42) is NotImplemented


class TestFileInfoStr:
    """__str__: проверяем ветки форматирования."""

    def test_minimal(self):
        result = FileInfo(url="u").__str__()
        assert "[Без имени]" in str(result)
        assert "неизвестно" in str(result)

    def test_with_file_name(self):
        result = FileInfo(url="u", file_name="test.jpg").__str__()
        assert "Имя файла: test.jpg" in str(result)

    def test_with_format(self):
        result = FileInfo(url="u", format="PNG").__str__()
        assert "Формат: PNG" in str(result)

    def test_with_dimensions(self):
        result = FileInfo(url="u", width=1920, height=1080).__str__()
        assert "1920×1080 пикс" in str(result)

    def test_with_duration(self):
        result = FileInfo(url="u", duration=120.5).__str__()
        assert "120.5 сек" in str(result)

    def test_with_fps(self):
        result = FileInfo(url="u", fps=29.97).__str__()
        assert "29.97 к/с" in str(result)

    def test_with_sample_rate(self):
        result = FileInfo(url="u", sample_rate=44100).__str__()
        assert "44100 Гц" in str(result)

    def test_with_bitrate_nominal(self):
        result = FileInfo(url="u", bitrate_nominal=320).__str__()
        assert "320 кбит/с" in str(result)

    def test_with_bitrate_avg(self):
        result = FileInfo(url="u", bitrate_avg=256).__str__()
        assert "256 кбит/с" in str(result)

    def test_with_parse_note(self):
        result = FileInfo(url="u", parse_note="some warning").__str__()
        assert "some warning" in str(result)

    def test_full(self):
        result = FileInfo(
            url="u",
            file_name="video.mp4",
            file_size=50_000_000,
            width=1920,
            height=1080,
            duration=120.0,
            fps=24.0,
            sample_rate=48000,
            bitrate_nominal=5000,
            bitrate_avg=4800,
            format="MP4",
            parse_note="ok",
        ).__str__()
        assert "video.mp4" in str(result)
        assert "Формат: MP4" in str(result)
        assert "1920×1080 пикс" in str(result)
        assert "120.0 сек" in str(result)
        assert "24.0 к/с" in str(result)
        assert "48000 Гц" in str(result)
        assert "5000 кбит/с" in str(result)
        assert "4800 кбит/с" in str(result)
        assert "ok" in str(result)
