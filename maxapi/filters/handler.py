from inspect import Signature, signature
from typing import Any, Callable

from magic_filter import MagicFilter

from ..context.state_machine import State
from ..enums.update import UpdateType
from ..filters.filter import BaseFilter
from ..filters.middleware import BaseMiddleware
from ..loggers import logger_dp
from ..types.updates import UpdateUnion


class Handler:
    """
    Обработчик события.

    Связывает функцию-обработчик с типом события, состояниями и фильтрами.
    """

    __slots__ = (
        "func_event",
        "signature",
        "update_type",
        "filters",
        "base_filters",
        "states",
        "middlewares",
    )

    _TYPE_MAP = (
        (State, "states"),
        (MagicFilter, "filters"),
        (BaseFilter, "base_filters"),
        (BaseMiddleware, "middlewares"),
    )

    def __init__(
        self,
        *args: Any,
        func_event: Callable,
        update_type: UpdateType,
        **kwargs: Any,
    ):
        """
        Создаёт обработчик события.

        Args:
            *args (Any): Список фильтров (MagicFilter, State, Command,
                BaseFilter, BaseMiddleware).
            func_event (Callable): Функция-обработчик.
            update_type (UpdateType): Тип обновления.
            **kwargs (Any): Дополнительные параметры.
        """

        self.func_event: Callable = func_event
        self.signature: Signature = signature(func_event)
        self.update_type: UpdateType = update_type

        self.filters: list[MagicFilter] = []
        self.base_filters: list[BaseFilter] = []
        self.states: list[State] = []
        self.middlewares: list[BaseMiddleware] = []

        for arg in self._sort_args(args):
            logger_dp.info(
                "Неизвестный фильтр `%s` при регистрации `%s`",
                arg,
                func_event.__name__,
            )

    def _sort_args(self, args: tuple[Any]) -> list[Any]:
        unknown: list[Any] = []
        for arg in args:
            if isinstance(arg, tuple):
                self._sort_args(arg)
                continue

            for cls, target in type(self)._TYPE_MAP:
                if isinstance(arg, cls):
                    getattr(self, target).append(arg)
                    break
            else:
                unknown.append(arg)
        return unknown

    def matches_event(
        self, event: UpdateUnion, current_state: str | State | None
    ) -> bool:
        """
        Проверяет, подходит ли обработчик для события (фильтры, состояние).

        Args:
            event: Событие.
            current_state : Текущее состояние.
        """
        if self.states and current_state not in self.states:
            return False

        if not all(f.resolve(event) for f in self.filters):
            return False

        if not all (f(event) for f in self.base_filters):
            return False

        return True

    async def __call__(
        self,
        event_object: UpdateUnion,
        data: dict[str, Any],
    ) -> Any:
        kwargs = {
            k: v for k, v in data.items() if k in self.signature.parameters
        }
        return await self.func_event(event_object, **kwargs)
