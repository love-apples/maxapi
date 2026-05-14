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


class StatesGroup:
    """
    Базовый класс для описания группы состояний FSM.

    Атрибуты должны быть экземплярами State. Метод `states()`
    возвращает список всех состояний в виде строк.
    """

    @staticmethod
    def _append_unique_state(
        states: list[str], seen: set[str], state: str
    ) -> None:
        if state not in seen:
            seen.add(state)
            states.append(state)

    @classmethod
    def _append_nested_states(
        cls,
        states: list[str],
        seen: set[str],
        group: type["StatesGroup"],
    ) -> None:
        child_prefix = f"{group.__name__}:"
        full_child_prefix = f"{cls.__name__}.{group.__name__}:"

        for state in group.states():
            cls._append_unique_state(states, seen, state)
            if state.startswith(child_prefix):
                cls._append_unique_state(
                    states,
                    seen,
                    f"{full_child_prefix}{state[len(child_prefix):]}",
                )

    @classmethod
    def states(cls) -> list[str]:
        """
        Получить список всех состояний в формате 'ИмяКласса:имя_состояния'.

        Returns:
            Список строковых представлений состояний
        """
        states: list[str] = []

        seen: set[str] = set()

        for base in cls.__bases__:
            if issubclass(base, StatesGroup) and base is not StatesGroup:
                for state in base.states():
                    cls._append_unique_state(states, seen, state)

        for attr in dir(cls):
            value = getattr(cls, attr)
            if isinstance(value, State):
                cls._append_unique_state(states, seen, str(value))
            elif (
                isinstance(value, type)
                and issubclass(value, StatesGroup)
                and value is not StatesGroup
            ):
                cls._append_nested_states(states, seen, value)

        return states
