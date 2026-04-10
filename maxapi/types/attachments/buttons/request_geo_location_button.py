from typing import Literal

from ....enums.button_type import ButtonType
from .button import Button


class RequestGeoLocationButton(Button):
    """
    Кнопка запроса геолокации пользователя.

    Attributes:
        quick: Если True, запрашивает геолокацию без дополнительного
               подтверждения пользователя (по умолчанию False)
    """

    type: Literal[ButtonType.REQUEST_GEO_LOCATION] = (
        ButtonType.REQUEST_GEO_LOCATION
    )
    quick: bool = False
