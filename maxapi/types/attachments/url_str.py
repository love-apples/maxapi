from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from ...utils.file_inspector import FileInspector


class UrlStr(str):
    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(),
        )

    async def get_info(self):
        inspector = FileInspector()
        return await inspector.inspect_url(self)
