from enum import auto, unique

from ._compat import StrEnum


@unique
class Intent(StrEnum):
    """
    Тип интента (намерения) кнопки.

    Используется для стилизации и логической классификации
    пользовательских действий.
    """

    DEFAULT = auto()
    POSITIVE = auto()
    NEGATIVE = auto()
