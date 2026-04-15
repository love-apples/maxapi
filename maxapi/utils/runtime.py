from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from ..bot import Bot

_SCALAR_TYPES = (str, bytes, bytearray, int, float, bool, type(None))


def _should_skip(value: Any, seen: set[int]) -> bool:
    if isinstance(value, _SCALAR_TYPES):
        return True

    value_id = id(value)
    if value_id in seen:
        return True

    seen.add(value_id)
    return False


def _bind_model(model: BaseModel, bot: Bot, seen: set[int]) -> BaseModel:
    for field_name in model.__class__.model_fields:
        bind_bot(getattr(model, field_name, None), bot, _seen=seen)

    return model


def bind_bot(value: Any, bot: Bot, *, _seen: set[int] | None = None) -> Any:
    """Рекурсивно внедрить ссылку на бота в модель и вложенные объекты."""

    seen = set() if _seen is None else _seen
    if _should_skip(value, seen):
        return value

    if hasattr(value, "bot"):
        value.bot = bot

    if isinstance(value, BaseModel):
        return _bind_model(value, bot, seen)

    if isinstance(value, dict):
        for nested in value.values():
            bind_bot(nested, bot, _seen=seen)
        return value

    if isinstance(value, (list, tuple, set, frozenset)):
        for nested in value:
            bind_bot(nested, bot, _seen=seen)

    return value
