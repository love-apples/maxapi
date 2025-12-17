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
                    "Неизвестный фильтр `%s` при регистрации `%s`",
                    arg,
                    func_event.__name__
                )

    async def __call__(
        self,
        event_object: UpdateUnion,
        data: dict[str, Any],
    ) -> Any:
        kwargs = {
            k: v for k, v in data.items() if k in self.signature.parameters
        }
        return await self.func_event(event_object, **kwargs)
