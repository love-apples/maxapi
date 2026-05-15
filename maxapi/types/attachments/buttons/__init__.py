from typing import Annotated

from pydantic import Field

from .button import Button
from .callback_button import CallbackButton
from .chat_button import ChatButton
from .clipboard_button import ClipboardButton
from .link_button import LinkButton
from .message_button import MessageButton
from .open_app_button import OpenAppButton
from .request_contact import RequestContactButton
from .request_geo_location_button import RequestGeoLocationButton

InlineButtonUnion = Annotated[
    CallbackButton
    | ChatButton
    | ClipboardButton
    | LinkButton
    | RequestContactButton
    | RequestGeoLocationButton
    | MessageButton
    | OpenAppButton,
    Field(discriminator="type"),
]

__all__ = [
    "Button",
    "CallbackButton",
    "ChatButton",
    "ClipboardButton",
    "InlineButtonUnion",
    "LinkButton",
    "MessageButton",
    "OpenAppButton",
    "RequestContactButton",
    "RequestGeoLocationButton",
]
