from pydantic import BaseModel

from ...enums.add_chat_members_error_code import (
    AddChatMembersErrorCode,
)


class FailedUserDetails(BaseModel):
    """
    Детали ошибки для пользователя.

    Attributes:
        error_code (str): Код ошибки.
        user_ids (List[int]): Список ID пользователей, для которых произошла
            ошибка.
    """

    error_code: AddChatMembersErrorCode
    user_ids: list[int]


class AddedMembersChat(BaseModel):
    """
    Ответ API при добавлении списка пользователей в чат.

    Attributes:
        success (bool): Статус успешности операции.
        message (Optional[str]): Дополнительное сообщение или ошибка.
    """

    success: bool
    message: str | None = None
    failed_user_ids: list[int] | None = None
    failed_user_details: list[FailedUserDetails] | None = None
