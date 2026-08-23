from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_core import core_schema
from url_media_probe import MediaInfo, MediaProbe

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic import GetCoreSchemaHandler
    from pydantic_core import CoreSchema


class UrlStr(str):
    __slots__ = ("media_probe",)
    media_probe: MediaProbe | None

    def __new__(cls, value: str):
        instance = super().__new__(cls, value)
        instance.media_probe = None
        return instance

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """
        Строит core-схему ``UrlStr`` (протокол pydantic v2).

        Метод вызывается pydantic автоматически при построении схемы
        модели с полем, аннотированным ``UrlStr``.

        Returns:
            CoreSchema: Схема ``str`` с валидатором, приводящим значение
            к экземпляру ``UrlStr``.
        """
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(),
        )

    async def get_info(
        self,
        *,
        timeout: int = 30,
        max_total: int = 256_000,
        max_retries: int = 3,
        raise_on_network_error: bool = False,
    ) -> MediaInfo:
        """
        Инспектирует удалённый файл по URL.

        Args:
            timeout: Таймаут HTTP-запроса в секундах.
            max_total: Максимальный объём скачанных данных (байт).
            max_retries: Число повторных попыток при ``retry_on_statuses``.
            raise_on_network_error: Пробрасывается в ``MediaProbe``: при
                True сетевая ошибка выбрасывается как исключение, при
                False (по умолчанию) возвращается MediaInfo со статусом
                "error".

        Returns:
            MediaInfo: Результат инспекции (в т.ч. при сетевой ошибке).

        Raises:
            aiohttp.ClientError: Сетевая ошибка при
                ``raise_on_network_error=True`` (пробрасывает MediaProbe).
        """
        self.media_probe = MediaProbe(raise_on_network=raise_on_network_error)
        return await self.media_probe.from_url(
            self, timeout=timeout, max_total=max_total, max_retries=max_retries
        )

    async def download_file(
        self,
        file_path: str | Path,
        *,
        file_name: str | None = None,
        timeout: int = 30,
        max_retries: int = 3,
    ) -> Path:
        """
        Сохраняет файл целиком на диск.

        Может вызываться без предварительного ``get_info()``: если
        инспекция ещё не выполнялась, сначала выполняется проба по
        одним заголовкам (тело не скачивается) — она устанавливает
        соединение и метаданные, файл докачивается при сохранении.
        Если ``get_info()`` уже вызывался, используется его пробник;
        закрытое соединение переоткрывается автоматически.

        Сетевые ошибки выбрасываются всегда: запросы повторяются до
        ``max_retries`` раз (обрывы соединения и статусы 429/5xx),
        после чего исключение пробрасывается вызывающему коду.

        Args:
            file_path: Директория для сохранения.
            file_name: Имя файла. Если не указано, используется
                ``meta.file_name`` из результата инспекции.
            timeout: Таймаут HTTP-запроса в секундах.
            max_retries: Число повторных попыток при обрывах и 429/5xx.

        Returns:
            Path: Путь к сохранённому файлу.

        Raises:
            aiohttp.ClientError: Сетевая ошибка после исчерпания ретраев.
        """
        probe = self.media_probe
        if probe is None:
            probe = MediaProbe(raise_on_network=True)
            self.media_probe = probe
            await probe.from_url(
                self,
                timeout=timeout,
                max_total=0,
                max_retries=max_retries,
            )
        return await probe.full_file_save(file_path, file_name=file_name)
