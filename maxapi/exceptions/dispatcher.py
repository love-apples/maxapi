from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(slots=True)
class HandlerException(Exception):
    handler_title: str
    router_id: str | int | None
    process_info: str
    memory_context: Dict[str, Any]
    cause: Optional[BaseException] = None

    def __str__(self) -> str:
        parts = [
            f"handler={self.handler_title!s}",
            f"router_id={self.router_id!s}",
            f"process={self.process_info}",
            f"context_keys={list(self.memory_context.keys())}",
        ]
        if self.cause:
            parts.append(
                f"cause={self.cause.__class__.__name__}: {self.cause}"
            )
        return "HandlerException(" + ", ".join(parts) + ")"


@dataclass(slots=True)
class MiddlewareException(Exception):
    middleware_title: str
    router_id: str | int | None
    process_info: str
    memory_context: Dict[str, Any]
    cause: Optional[BaseException] = None

    def __str__(self) -> str:
        parts = [
            f"middleware={self.middleware_title!s}",
            f"router_id={self.router_id!s}",
            f"process={self.process_info}",
            f"context_keys={list(self.memory_context.keys())}",
        ]
        if self.cause:
            parts.append(
                f"cause={self.cause.__class__.__name__}: {self.cause}"
            )
        return "MiddlewareException(" + ", ".join(parts) + ")"
