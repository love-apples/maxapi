from typing import Literal

from ....enums.button_type import ButtonType
from .button import Button


class LinkButton(Button):
    """
    Кнопка с внешней ссылкой.

    Attributes:
        url: Ссылка для перехода (должна содержать http/https)
    """

    type: Literal[ButtonType.LINK] = ButtonType.LINK
    url: str | None = None
