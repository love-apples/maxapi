from enum import Enum


class AddChatMembersErrorCode(str, Enum):
    """
    Коды ошибок при добавлении участников в чат.
    """

    ADD_PARTICIPANT_PRIVACY = "add.participant.privacy"
    ADD_PARTICIPANT_NOT_FOUND = "add.participant.not.found"
