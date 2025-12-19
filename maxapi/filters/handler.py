from collections.abc import Callable
from inspect import Signature, signature
from typing import Any

from magic_filter import MagicFilter

from ..context.state_machine import State
from ..enums.update import UpdateType
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
        "states",
        "middlewares",
    )

    _TYPE_RULES = (
        (lambda x: isinstance(x, State), "states"),
        (lambda x: isinstance(x, BaseMiddleware), "middlewares"),
        (callable, "filters"),
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
            *args: Список фильтров и/или мидлваров (State, Callable,
                MagicFilter, BaseMiddleware).
            func_event: Функция-обработчик.
            update_type: Тип обновления.
            **kwargs: Дополнительные параметры.
        """

        self.func_event: Callable = func_event
        self.signature: Signature = signature(func_event)
        self.update_type: UpdateType = update_type

        self.filters: list[Callable] = []
        self.states: list[State] = []
        self.middlewares: list[BaseMiddleware] = []

        self._sort_args(args)

    def _sort_args(self, args: tuple[Any]):
        for arg in args:
            if isinstance(arg, tuple):
                for item in arg:
                    self._handle_arg(item)
            else:
                self._handle_arg(arg)

    def _handle_arg(self, arg: Any):
        for predicate, target in type(self)._TYPE_RULES:
            if predicate(arg):
                getattr(self, target).append(arg)
                break
        else:
            logger_dp.info(
                "Неизвестный фильтр `%s` при регистрации `%s`",
                arg,
                self.func_event.__name__,
            )

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

        for f in self.filters:
            if isinstance(f, MagicFilter):
                r = f.resolve(event)
            else:
                r = f(event)

            if not r:
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
