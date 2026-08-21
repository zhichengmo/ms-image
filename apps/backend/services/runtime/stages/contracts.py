"""Frozen-context contracts for internal Runtime Stage handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from apps.backend.core.pipeline import StageResult


class StageHandlerContractError(ValueError):
    """Raised when a frozen Stage context cannot satisfy a handler contract."""


@dataclass(frozen=True)
class StageExecutionContext:
    """Task and checkpoint facts frozen before a handler produces its result."""

    task: Any
    stage: Any


class StageHandler(Protocol):
    """Versioned implementation selected by a persisted handler key/version."""

    handler_key: str
    handler_version: str

    async def execute(self, context: StageExecutionContext) -> StageResult:
        """Return a business result without advancing Task or Stage state."""


__all__ = [
    "StageExecutionContext",
    "StageHandler",
    "StageHandlerContractError",
]
