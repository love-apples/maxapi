from enum import Enum


class Intent(str, Enum):
    """
    Тип интента (намерения) кнопки.

    Используется для стилизации и логической классификации пользовательских действий.
    """

    DEFAULT = "default"
    POSITIVE = "positive"
    NEGATIVE = "negative"
