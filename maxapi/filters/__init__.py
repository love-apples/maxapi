from magic_filter import MagicFilter

from .filter import BaseFilter

F = MagicFilter()

__all__ = ["BaseFilter"]


def filter_attrs(obj: object, *filters: MagicFilter) -> bool:
    """
    Применяет один или несколько фильтров MagicFilter к объекту.

    Args:
        obj (object): Объект, к которому применяются фильтры (например, event или message).
        *filters (MagicFilter): Один или несколько выражений MagicFilter.

    Returns:
        bool: True, если все фильтры возвращают True, иначе False.
    """

    try:
        return all(f.resolve(obj) for f in filters)
    except Exception:
        return False
