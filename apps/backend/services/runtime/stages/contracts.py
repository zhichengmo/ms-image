"""Frozen-context contracts for internal Runtime Stage handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from apps.backend.core.ai.model_route import AiModelRoute
from apps.backend.core.pipeline import StageResult
from apps.backend.services.runtime.stages.xray.prompt_commands import XRayPromptCommand


class StageHandlerContractError(ValueError):
    """Raised when a frozen Stage context cannot satisfy a handler contract."""


@dataclass(frozen=True)
class StageExecutionContext:
    """Task and checkpoint facts frozen before a handler produces its result."""

    task: Any
    stage: Any


@dataclass(frozen=True)
class StageAIRequest:
    """Pure AI request intent; persistence and transport remain Worker-owned."""

    prompt_command: XRayPromptCommand
    prompt_key: str
    route: AiModelRoute
    module_code: str = "xray"
    locale: str = "zh-CN"
    variant: str = "default"


@dataclass(frozen=True)
class StageExecutionPlan:
    """Exactly one provider-free result or one AI request intent."""

    completed_result: StageResult | None = None
    ai_request: StageAIRequest | None = None

    def __post_init__(self) -> None:
        if (self.completed_result is None) == (self.ai_request is None):
            raise StageHandlerContractError("stage_execution_plan_invalid")


class StageHandler(Protocol):
    """Versioned implementation selected by a persisted handler key/version."""

    handler_key: str
    handler_version: str

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        """Build a pure execution plan without DB or Provider side effects."""


class AIStageHandler(StageHandler, Protocol):
    """AI Stage additionally converts a durable Logical Call into a result."""

    def consume_ai_call(
        self,
        context: StageExecutionContext,
        call_result: Mapping[str, Any],
    ) -> StageResult:
        """Consume accepted or terminal failed Logical Call facts."""


__all__ = [
    "AIStageHandler",
    "StageAIRequest",
    "StageExecutionContext",
    "StageExecutionPlan",
    "StageHandler",
    "StageHandlerContractError",
]
