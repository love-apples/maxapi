from datetime import datetime, timezone

from maxapi.utils.time import to_ms, from_ms


def test_to_ms_with_datetime_aware():
    dt = datetime.fromtimestamp(1234567890, tz=timezone.utc)
    assert to_ms(dt) == 1234567890000


def test_to_ms_with_int_and_float():
    assert to_ms(123) == 123
    assert to_ms(123.9) == 123


def test_from_ms_roundtrip():
    ms = 1600000000123
    dt = from_ms(ms)
    assert dt is not None
    assert to_ms(dt) == ms


def test_from_ms_none():
    assert from_ms(None) is None
