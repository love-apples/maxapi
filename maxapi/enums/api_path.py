from enum import unique

from ._compat import StrEnum


@unique
class ApiPath(StrEnum):
    """
    Перечисление всех доступных API-эндпоинтов.

    Используется для унифицированного указания путей при отправке запросов.
    """

    ME = "/me"
    CHATS = "/chats"
    MESSAGES = "/messages"
    UPDATES = "/updates"
    VIDEOS = "/videos"
    ANSWERS = "/answers"
    ACTIONS = "/actions"
    PIN = "/pin"
    MEMBERS = "/members"
    ADMINS = "/admins"
    UPLOADS = "/uploads"
    SUBSCRIPTIONS = "/subscriptions"
