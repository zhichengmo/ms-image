"""Common final-result selection Stage."""

from __future__ import annotations

from apps.backend.core.pipeline import StageResult
from apps.backend.services.runtime.stages.contracts import (
    StageExecutionContext,
    StageHandlerContractError,
)


class DecisionFinalizationStageHandler:
    """Produce the immutable finalization payload; execution owns Report persistence."""

    handler_key = "decision_finalization"
    handler_version = "v1"

    async def execute(self, context: StageExecutionContext) -> StageResult:
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("decision_finalization_stage_invalid")
        return StageResult(
            status="completed",
            output={
                "medical_status": "not_produced",
                "selected_owner": "primary",
                "source_stage_id": (stage.input_json or {}).get("previous_stage_id"),
                "provider_called": False,
            },
        )


__all__ = ["DecisionFinalizationStageHandler"]
