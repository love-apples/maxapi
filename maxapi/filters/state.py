from __future__ import annotations

from collections.abc import Iterable
from inspect import isclass
from typing import TYPE_CHECKING, Any, TypeAlias, cast

from ..context.state_machine import State, StatesGroup
from .filter import BaseFilter

if TYPE_CHECKING:
    from ..types.updates import UpdateUnion

StateType: TypeAlias = State | str | None | StatesGroup | type[StatesGroup]
StateInput: TypeAlias = StateType | Iterable[StateType]
_UNSET = object()


class StateFilter(BaseFilter):
    """
    Фильтр текущего FSM-состояния.

    Поддерживает одиночные состояния, несколько состояний, ``None`` для
    отсутствующего состояния, ``"*"`` для любого состояния и ``StatesGroup``.
    """

    def __init__(
        self,
        *states: StateInput,
        exclude: StateInput | object = _UNSET,
    ) -> None:
        normalized_states = self._normalize_states(states)
        if not normalized_states:
            raise ValueError(
                "Нужно передать хотя бы одно состояние. "
                'Используйте StateFilter("*") для любого состояния '
                "или StateFilter(None) для отсутствующего состояния."
            )

        self.states = normalized_states
        self.exclude = (
            ()
            if exclude is _UNSET or exclude is None
            else self._normalize_states((cast(StateInput, exclude),))
        )

    @staticmethod
    def _is_states_group_class(value: Any) -> bool:
        return isclass(value) and issubclass(value, StatesGroup)

    @classmethod
    def _is_state_iterable(cls, value: Any) -> bool:
        if isinstance(value, (str, State, StatesGroup)) or value is None:
            return False
        if cls._is_states_group_class(value):
            return False
        return isinstance(value, Iterable)

    @classmethod
    def _normalize_states(
        cls, states: tuple[StateInput, ...]
    ) -> tuple[Any, ...]:
        normalized_states: list[Any] = []

        def append_state(state: Any) -> None:
            if cls._is_state_iterable(state):
                for item in cast(Iterable[Any], state):
                    append_state(item)
            else:
                normalized_states.append(state)

        for state in states:
            append_state(state)

        return tuple(normalized_states)

    @classmethod
    def _state_to_storage_value(cls, state: Any) -> Any:
        if isinstance(state, State):
            return str(state) or None

        return state

    @classmethod
    def _matches_state(cls, allowed_state: Any, raw_state: Any) -> bool:
        storage_state = cls._state_to_storage_value(raw_state)

        if isinstance(allowed_state, str) or allowed_state is None:
            return allowed_state == "*" or storage_state == allowed_state

        if isinstance(allowed_state, State):
            allowed_value = cls._state_to_storage_value(allowed_state)
            return allowed_value == "*" or storage_state == allowed_value

        if cls._is_states_group_class(allowed_state):
            return storage_state in allowed_state.states()

        if isinstance(allowed_state, StatesGroup):
            return storage_state in allowed_state.states()

        return storage_state == allowed_state

    def _matches_any(self, states: tuple[Any, ...], raw_state: Any) -> bool:
        return any(
            self._matches_state(allowed_state, raw_state)
            for allowed_state in states
        )

    def __str__(self) -> str:
        states = ", ".join(map(str, self.states))
        if not self.exclude:
            return f"{type(self).__name__}({states})"

        exclude = ", ".join(map(str, self.exclude))
        return f"{type(self).__name__}({states}, exclude={exclude})"

    async def __call__(
        self, event: UpdateUnion, raw_state: Any = None, **kwargs: Any
    ) -> bool | dict[str, Any]:
        if self.exclude and self._matches_any(self.exclude, raw_state):
            return False

        return self._matches_any(self.states, raw_state)
