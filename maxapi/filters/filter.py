from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types.updates import UpdateUnion


class BaseFilter:
    async def __call__(self, event: UpdateUnion) -> bool | dict:
        return True