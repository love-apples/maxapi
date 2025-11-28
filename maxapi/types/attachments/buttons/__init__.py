from typing import Union

from .callback_button import CallbackButton
from .chat_button import ChatButton
from .link_button import LinkButton
from .message_button import MessageButton
from .open_app_button import OpenAppButton
from .request_contact import RequestContactButton
from .request_geo_location_button import RequestGeoLocationButton

InlineButtonUnion = Union[
    CallbackButton,
    ChatButton,
    LinkButton,
    RequestContactButton,
    RequestGeoLocationButton,
    MessageButton,
    OpenAppButton,
]
