from enum import unique

from ._compat import StrEnum


@unique
class AddChatMembersErrorCode(StrEnum):
    """
    Коды ошибок при добавлении участников в чат.
    """

    ADD_PARTICIPANT_PRIVACY = "add.participant.privacy"
    ADD_PARTICIPANT_NOT_FOUND = "add.participant.not.found"
