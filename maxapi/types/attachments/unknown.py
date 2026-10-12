from typing import Any

from pydantic import ConfigDict

from .attachment import Attachment


class UnknownAttachment(Attachment):
    """
    Вложение типа, который библиотека пока не поддерживает.

    Сюда попадает вложение, чей ``type`` отсутствует в
    :class:`~maxapi.enums.attachment.AttachmentType`, например
    новый тип, который MAX ещё не описал в Bot API. Такое вложение
    не ломает разбор всего сообщения и сохраняется как есть: все
    поля из ответа API доступны как атрибуты модели.

    Attributes:
        type: Тип вложения из ответа API.
        payload: Полезная нагрузка в исходном виде.
    """

    type: str  # type: ignore[assignment]  # pyright: ignore[reportIncompatibleVariableOverride]
    payload: Any = None

    model_config = ConfigDict(extra="allow")
