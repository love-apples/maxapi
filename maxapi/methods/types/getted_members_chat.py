from typing import List, Optional

from pydantic import BaseModel

from ...types.chats import ChatMember


class GettedMembersChat(BaseModel):
    """
    Ответ API с полученным списком участников чата.

    Attributes:
        members (List[ChatMember]): Список участников с правами администратора.
        marker (Optional[int]): Маркер для постраничной навигации (если есть).
    """

    members: List[ChatMember]
    marker: Optional[int] = None
