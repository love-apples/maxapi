from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_core import core_schema

from ...utils.file_inspector import FileInspector

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic import GetCoreSchemaHandler
    from pydantic_core import CoreSchema

    from maxapi.types.file_info import FileInfo


class UrlStr(str):
    __slots__ = ("inspector",)
    inspector: FileInspector | None

    def __new__(cls, value: str):
        instance = super().__new__(cls, value)
        instance.inspector = None
        return instance

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
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
    ) -> FileInfo:
        """
        Инспектирует удалённый файл по URL.

        Args:
            timeout: Таймаут HTTP-запроса в секундах.
            max_total: Максимальный объём скачанных данных (байт).
            max_retries: Число повторных попыток при ``retry_on_statuses``.

        Returns:
            FileInfo: Результат инспекции (в т.ч. при сетевой ошибке).
        """
        self.inspector = FileInspector()
        return await self.inspector.inspect_url(
            self, timeout=timeout, max_total=max_total, max_retries=max_retries
        )

    async def full_file_save(
        self,
        file_path: str | Path,
        *,
        file_name: str | None = None,
    ) -> Path:
        """
        Сохраняет файл целиком на диск, используя уже полученные данные
        и активное соединение после get_info() для докачки недостающих данных.
        Если соединение закрыто, то создаётся новое.

        Args:
            file_path: Директория для сохранения.
            file_name: Имя файла. Если не указано, используется
                ``meta.file_name`` из результата инспекции.

        Returns:
            Path: Абсолютный путь к сохранённому файлу.
        """
        if not self.inspector:
            self.inspector = FileInspector()
        return await self.inspector.full_file_save(
            file_path, file_name=file_name
        )
