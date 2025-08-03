from typing import Callable, List, Optional

from magic_filter import MagicFilter

from ..filters.filter import BaseFilter
from ..filters.middleware import BaseMiddleware

from ..context.state_machine import State

from ..enums.update import UpdateType

from ..loggers import logger_dp


class Handler:
    
    """
    Обработчик события.

    Позволяет связать функцию-обработчик с типом обновления, состоянием и набором фильтров.
    """

    def __init__(
            self,
            *args,
            func_event: Callable,
            update_type: UpdateType,
            **kwargs
        ):
        
        """
        Инициализация обработчика.

        :param args: Список фильтров и состояний, в том числе:
            - MagicFilter — фильтр события,
            - State — состояние FSM,
            - Command — команда для фильтрации по началу текста сообщения.
        :param func_event: Функция-обработчик события
        :param update_type: Тип обновления (события), на которое подписан обработчик
        :param kwargs: Дополнительные параметры (не используются)
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
                logger_dp.info(f'Обнаружен неизвестный фильтр `{arg}` при ' 
                               f'регистрации функции `{func_event.__name__}`')