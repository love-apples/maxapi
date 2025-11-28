from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Type,
    Union,
)

from magic_filter import MagicFilter
from pydantic import BaseModel

from ..types.updates import UpdateUnion
from ..types.updates.message_callback import MessageCallback
from .filter import BaseFilter

PAYLOAD_MAX = 1024


class CallbackPayload(BaseModel):
    """
    Базовый класс для сериализации/десериализации callback payload.

    Атрибуты:
        prefix (str): Префикс для payload (используется при pack/unpack) (по умолчанию название класса).
        separator (str): Разделитель между значениями (по умолчанию '|').
    """

    if TYPE_CHECKING:
        prefix: ClassVar[str]
        separator: ClassVar[str]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """
        Автоматически проставляет prefix и separator при наследовании.
        """

        cls.prefix = kwargs.get("prefix", str(cls.__name__))
        cls.separator = kwargs.get("separator", "|")

    def pack(self) -> str:
        """
        Собирает данные payload в строку для передачи в callback payload.

        Raises:
            ValueError: Если в значении встречается разделитель или payload слишком длинный.

        Returns:
            str: Сериализованный payload.
        """

        values = [self.prefix]

        for name in self.attrs():
            value = getattr(self, name)
            str_value = "" if value is None else str(value)
            if self.separator in str_value:
                raise ValueError(
                    f'Символ разделителя "{self.separator}" не должен встречаться в значении поля {name}'
                )

            values.append(str_value)

        data = self.separator.join(values)

        if len(data.encode()) > PAYLOAD_MAX:
            raise ValueError(
                f"Payload слишком длинный! Максимум: {PAYLOAD_MAX} байт"
            )

        return data

    @classmethod
    def unpack(cls, data: str) -> "CallbackPayload":
        """
        Десериализует payload из строки.

        Args:
            data (str): Строка payload (из callback payload).

        Raises:
            ValueError: Некорректный prefix или количество аргументов.

        Returns:
            CallbackPayload: Экземпляр payload с заполненными полями.
        """

        parts = data.split(cls.separator)

        if not parts[0] == cls.prefix:
            raise ValueError("Некорректный prefix")

        field_names = cls.attrs()

        if not len(parts) - 1 == len(field_names):
            raise ValueError(
                f"Ожидалось {len(field_names)} аргументов, получено {len(parts) - 1}"
            )

        kwargs = dict(zip(field_names, parts[1:]))
        return cls(**kwargs)

    @classmethod
    def attrs(cls) -> List[str]:
        """
        Возвращает список полей для сериализации/десериализации (исключая prefix и separator).

        Returns:
            List[str]: Имена полей модели.
        """

        return [
            k
            for k in cls.model_fields.keys()
            if k not in ("prefix", "separator")
        ]

    @classmethod
    def filter(cls, rule: Optional[MagicFilter] = None) -> PayloadFilter:
        """
        Создаёт PayloadFilter для фильтрации callback-ивентов по payload.

        Args:
            rule (Optional[MagicFilter]): Фильтр на payload.

        Returns:
            PayloadFilter: Экземпляр фильтра для хэндлера.
        """

        return PayloadFilter(model=cls, rule=rule)


class PayloadFilter(BaseFilter):
    """
    Фильтр для MessageCallback по payload.
    """

    def __init__(
        self, model: Type[CallbackPayload], rule: Optional[MagicFilter]
    ):
        """
        Args:
            model (Type[CallbackPayload]): Класс payload для распаковки.
            rule (Optional[MagicFilter]): Фильтр (условие) для payload.
        """

        self.model = model
        self.rule = rule

    async def __call__(
        self, event: UpdateUnion
    ) -> Union[Dict[str, Any], bool]:
        """
        Проверяет event на MessageCallback и применяет фильтр к payload.

        Args:
            event (UpdateUnion): Обновление/событие.

        Returns:
            dict | bool: dict с payload при совпадении, иначе False.
        """

        if not isinstance(event, MessageCallback):
            return False

        if not event.callback.payload:
            return False

        try:
            payload = self.model.unpack(event.callback.payload)
        except Exception:
            return False

        if not self.rule or self.rule.resolve(payload):
            return {"payload": payload}

        return False
