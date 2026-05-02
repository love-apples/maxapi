from collections.abc import Callable
from typing import Any

from magic_filter import MagicFilter

from ..context.state_machine import State
from ..enums.update import UpdateType
from ..filters.filter import BaseFilter
from ..filters.middleware import BaseMiddleware, HandlerCallable
from ..loggers import logger_dp


class Handler:
    """
    Обработчик события.

    Связывает функцию-обработчик с типом события, состояниями и фильтрами.
    """

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
            *args: Список фильтров (MagicFilter, State, Command,
                BaseFilter, BaseMiddleware).
            func_event: Функция-обработчик.
            update_type: Тип обновления.
            **kwargs: Дополнительные параметры.
        """

        self.func_event: Callable = func_event
        self.update_type: UpdateType = update_type
        self.filters: list[MagicFilter] = []
        self.base_filters: list[BaseFilter] = []

        states_kwargs = kwargs.pop("states", [])
        self.states: list[State | None]
        if isinstance(states_kwargs, (list, tuple, set)):
            self.states = list(states_kwargs)
        else:
            self.states = [states_kwargs]

        self.middlewares: list[BaseMiddleware] = []

        self.func_args: frozenset[str] | None = None
        self.mw_chain: HandlerCallable | None = None

        for arg in args:
            if isinstance(arg, MagicFilter):
                self.filters.append(arg)
            elif isinstance(arg, State) or arg is None:
                self.states.append(arg)
            elif isinstance(arg, BaseMiddleware):
                self.middlewares.append(arg)
            elif isinstance(arg, BaseFilter):
                self.base_filters.append(arg)
            else:
                logger_dp.info(
                    f"Неизвестный фильтр `{arg}` "
                    f"при регистрации `{func_event.__name__}`"
                )
