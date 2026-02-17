from ....enums.button_type import ButtonType
from .button import Button


class OpenAppButton(Button):
    """
    Кнопка для открытия приложения

    Attributes:
        text: Видимый текст кнопки
        web_app: Публичное имя (username) бота или ссылка на него, чьё мини-приложение надо запустить
        contact_id: Идентификатор бота, чьё мини-приложение надо запустить
        payload: Параметр запуска, который будет передан в initData мини-приложения
    """

    type: ButtonType = ButtonType.OPEN_APP
    text: str
    web_app: str | None = None
    contact_id: int | None = None
    payload: str | None = None
