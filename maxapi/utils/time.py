from datetime import datetime
from typing import Optional, Union


def to_ms(value: Union[datetime, int, float]) -> int:
    """Преобразует datetime или числовую метку времени в миллисекунды (int).

    Если `value` — объект datetime, возвращает int(timestamp * 1000).
    Если `value` — int или float (уже временная метка), возвращает int(value).
    """
    if isinstance(value, datetime):
        return int(value.timestamp() * 1000)
    return int(value)


def from_ms(value: Optional[Union[int, float]]) -> Optional[datetime]:
    """Преобразует миллисекунды с эпохи в объект datetime.

    Если value равен None, возвращает None.
    Иначе возвращает datetime.fromtimestamp(value / 1000).
    """
    if value is None:
        return None
    return datetime.fromtimestamp(int(value) / 1000)
