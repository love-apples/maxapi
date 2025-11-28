from enum import Enum


class ApiPath(str, Enum):
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
