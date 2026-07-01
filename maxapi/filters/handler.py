from collections.abc import Callable
from inspect import isclass
from typing import Any

from magic_filter import MagicFilter

from ..context.state_machine import State, StatesGroup
from ..enums.update import UpdateType
from ..filters.exception_type import ExceptionTypeFilter
from ..filters.filter import BaseFilter
from ..filters.middleware import BaseMiddleware, HandlerCallable
from ..filters.state import StateFilter
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
        self.states: list[Any]
        if isinstance(states_kwargs, (list, tuple, set)):
            self.states = list(states_kwargs)
        else:
            self.states = [states_kwargs]

        self.middlewares: list[BaseMiddleware] = []
        self.state_filter: StateFilter | None = None

        self.func_args: frozenset[str] | None = None
        self.mw_chain: HandlerCallable | None = None

        for arg in args:
            if isinstance(arg, MagicFilter):
                self.filters.append(arg)
            elif (
                isinstance(arg, State)
                or arg is None
                or (isclass(arg) and issubclass(arg, StatesGroup))
                or isinstance(arg, StatesGroup)
            ):
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

        self.prepare_state_filter()

    def prepare_state_filter(self) -> None:
        """Подготавливает фильтр состояний для hot-path dispatch."""
        self.state_filter = StateFilter(self.states) if self.states else None


class ErrorHandler:
    """
    Обработчик ошибки диспетчера.

    Используется декораторами ``Dispatcher.errors`` и ``Router.errors``.
    """

    def __init__(self, *args: Any, func_event: Callable) -> None:
        """
        Создаёт обработчик ошибки.

        Args:
            *args: Типы исключений, MagicFilter или BaseFilter.
            func_event: Функция-обработчик ошибки.
        """
        self.func_event: Callable = func_event
        self.filters: list[MagicFilter] = []
        self.base_filters: list[BaseFilter] = []
        self.func_args: frozenset[str] | None = None

        exception_types: list[type[BaseException]] = []

        for arg in args:
            if isinstance(arg, MagicFilter):
                self.filters.append(arg)
            elif isinstance(arg, BaseFilter):
                self.base_filters.append(arg)
            elif isclass(arg) and issubclass(arg, BaseException):
                exception_types.append(arg)
            else:
                logger_dp.info(
                    f"Неизвестный фильтр ошибки `{arg}` "
                    f"при регистрации `{func_event.__name__}`"
                )

        if exception_types:
            self.base_filters.insert(0, ExceptionTypeFilter(*exception_types))
