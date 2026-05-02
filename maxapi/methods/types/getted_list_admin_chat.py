from pydantic import BaseModel

from ...types.chats import ChatMember


class GettedListAdminChat(BaseModel):
    """
    Ответ API с полученным списком администраторов чата.

    Attributes:
        members: Список участников с правами администратора.
        marker: Маркер для постраничной навигации (если есть).
    """

    members: list[ChatMember]
    marker: int | None = None
