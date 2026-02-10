from typing import List


class State:
    """
    Представляет отдельное состояние в FSM-группе.

    При использовании внутри StatesGroup, автоматически присваивает
    уникальное имя в формате 'ИмяКласса:имя_поля'.
    """

    def __init__(self) -> None:
        self.name: str | None = None

    def __set_name__(self, owner: type, attr_name: str) -> None:
        self.name = f"{owner.__name__}:{attr_name}"

    def __str__(self) -> str:
        return self.name or ""

    def __repr__(self) -> str:
        return f"State(name={self.name!r})"

    def __eq__(self, value: object, /) -> bool:
        if value is None:
            return False
        if isinstance(value, State):
            return self.name == value.name
        if isinstance(value, str):
            return self.name == value
        raise NotImplementedError(
            f"Сравнение `State` с типом {type(value)} невозможно"
        )

    def __hash__(self) -> int:
        return hash(self.name)


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
