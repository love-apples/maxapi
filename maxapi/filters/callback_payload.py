from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    ClassVar,
)

from pydantic import BaseModel

from ..filters.middleware import BaseMiddleware

PAYLOAD_MAX = 1024


class CallbackPayload(BaseModel):
    """
    Базовый класс для сериализации/десериализации callback payload.

    Атрибуты:
        prefix: Префикс для payload (используется при pack/unpack) (по
            умолчанию название класса).
        separator: Разделитель между значениями (по умолчанию '|').
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
            ValueError: Если в значении встречается разделитель или payload
                слишком длинный.

        Returns:
            str: Сериализованный payload.
        """

        values = [self.prefix]

        for name in self.attrs():
            value = getattr(self, name)
            str_value = "" if value is None else str(value)
            if self.separator in str_value:
                raise ValueError(
                    f"Символ разделителя '{self.separator}' не должен "
                    f"встречаться в значении поля {name}"
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
            data: Строка payload (из callback payload).

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
                f"Ожидалось {len(field_names)} аргументов, получено "
                f"{len(parts) - 1}"
            )

        kwargs = dict(zip(field_names, parts[1:]))
        return cls(**kwargs)

    @classmethod
    def attrs(cls) -> list[str]:
        """
        Вернуть список полей для (де)сериализации (без prefix и separator).

        Returns:
            Имена полей модели.
        """

        return [
            k
            for k in cls.model_fields.keys()
            if k not in ("prefix", "separator")
        ]

    @classmethod
    def provide(cls) -> ProvidePayload:
        """
        Создаёт ProvidePayload для предоставления параметра payload хэндлеру.

        Returns:
            Экземпляр мидлвар для хэндлера.
        """

        return ProvidePayload(model=cls)

class ProvidePayload(BaseMiddleware):
    __slots__ = ("model",)

    def __init__(self, model: type[CallbackPayload]):
        self.model = model

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event_object: Any,
        data: dict[str, Any],
    ) -> Any:
        data["payload"] = self.model.unpack(event_object.callback.payload)
        return await handler(event_object, data)
