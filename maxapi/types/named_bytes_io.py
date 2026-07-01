from io import BytesIO


class NamedBytesIO(BytesIO):
    """
    BytesIO с поддержкой атрибута .name для единообразия с файловыми объектами.
    """

    __slots__ = ("name",)
    name: str | None

    def __init__(
        self, buffer: bytes = b"", *, name: str | None = None
    ) -> None:
        super().__init__(buffer)
        self.name = name  # Соответствует протоколу typing.BinaryIO
