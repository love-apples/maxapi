from pydantic import BaseModel

from ...types.comment import CommentMessage


class SendedComment(BaseModel):
    """
    Ответ API с отправленным комментарием.

    Attributes:
        message: Объект отправленного комментария.
    """

    message: CommentMessage
