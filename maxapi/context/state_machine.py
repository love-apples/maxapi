from typing import List


class State:
    """
    Представляет отдельное состояние в FSM-группе.

    При использовании внутри StatesGroup, автоматически присваивает уникальное имя в формате 'ИмяКласса:имя_поля'.
    """

    def __init__(self):
        self.name = None

    def __set_name__(self, owner: type, attr_name: str):
        self.name = f"{owner.__name__}:{attr_name}"

    def __str__(self):
        return self.name


class StatesGroup:
    """
    Базовый класс для описания группы состояний FSM.

    Атрибуты должны быть экземплярами State. Метод `states()` возвращает список всех состояний в виде строк.
    """

    @classmethod
    def states(cls) -> List[str]:
        """
        Получить список всех состояний в формате 'ИмяКласса:имя_состояния'.

        Returns:
            Список строковых представлений состояний
        """

        return [
            str(getattr(cls, attr))
            for attr in dir(cls)
            if isinstance(getattr(cls, attr), State)
        ]
