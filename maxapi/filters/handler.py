from typing import Any, Callable, List, Optional

from magic_filter import MagicFilter

from ..context.state_machine import State
from ..enums.update import UpdateType
from ..filters.filter import BaseFilter
from ..filters.middleware import BaseMiddleware
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
            *args (Any): Список фильтров (MagicFilter, State, Command, BaseFilter, BaseMiddleware).
            func_event (Callable): Функция-обработчик.
            update_type (UpdateType): Тип обновления.
            **kwargs (Any): Дополнительные параметры.
        """

        self.func_event: Callable = func_event
        self.update_type: UpdateType = update_type
        self.filters: Optional[List[MagicFilter]] = []
        self.base_filters: Optional[List[BaseFilter]] = []
        self.states: Optional[List[State]] = []
        self.middlewares: List[BaseMiddleware] = []

        for arg in args:
            if isinstance(arg, MagicFilter):
                self.filters.append(arg)
            elif isinstance(arg, State):
                self.states.append(arg)
            elif isinstance(arg, BaseMiddleware):
                self.middlewares.append(arg)
            elif isinstance(arg, BaseFilter):
                self.base_filters.append(arg)
            else:
                logger_dp.info(
                    f"Неизвестный фильтр `{arg}` при регистрации `{func_event.__name__}`"
                )
