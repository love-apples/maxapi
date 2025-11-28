from enum import Enum


class ButtonType(str, Enum):
    """
    Типы кнопок, доступных в интерфейсе бота.

    Определяют поведение при нажатии на кнопку в сообщении.
    """

    REQUEST_CONTACT = "request_contact"
    CALLBACK = "callback"
    LINK = "link"
    REQUEST_GEO_LOCATION = "request_geo_location"
    CHAT = "chat"
    MESSAGE = "message"
    OPEN_APP = "open_app"
