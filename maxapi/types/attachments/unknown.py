from typing import Any

from pydantic import ConfigDict

from .attachment import Attachment


class UnknownAttachment(Attachment):
    """
    Вложение типа, который библиотека пока не поддерживает.

    MAX добавляет новые типы вложений (например, опросы) раньше, чем
    они появляются в документации Bot API. Чтобы такое вложение не
    ломало разбор всего сообщения, оно сохраняется как есть: все
    поля из ответа API доступны как атрибуты модели.

    Attributes:
        type: Тип вложения из ответа API.
        payload: Полезная нагрузка в исходном виде.
    """

    type: str  # type: ignore[assignment]  # pyright: ignore[reportIncompatibleVariableOverride]
    payload: Any = None

    model_config = ConfigDict(extra="allow")
