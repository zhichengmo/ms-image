"""Common final-result selection Stage."""

from __future__ import annotations

from apps.backend.core.pipeline import StageResult
from apps.backend.services.runtime.stages.contracts import (
    StageExecutionContext,
    StageExecutionPlan,
    StageHandlerContractError,
)


class DecisionFinalizationStageHandler:
    """Produce finalization content from the previous accepted Stage output."""

    handler_key = "decision_finalization"
    handler_version = "v1"

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("decision_finalization_stage_invalid")
        previous_output = (stage.input_json or {}).get("previous_output") or {}
        output = {
            "medical_status": previous_output.get("medical_status", "not_produced"),
            "selected_owner": (
                "targeted"
                if previous_output.get("candidate_kind") == "targeted"
                else "primary"
            ),
            "source_stage_id": (stage.input_json or {}).get("previous_stage_id"),
            "source_call_id": previous_output.get("source_call_id"),
            "provider_called": previous_output.get("medical_status") == "produced",
        }
        if isinstance(previous_output.get("complete_medical_result"), dict):
            output["complete_medical_result"] = previous_output[
                "complete_medical_result"
            ]
        return StageExecutionPlan(
            completed_result=StageResult(status="completed", output=output)
        )


class DecisionFinalizationV2StageHandler(DecisionFinalizationStageHandler):
    """Version-isolated v2 finalizer preserving the model result verbatim."""

    handler_version = "v2"


__all__ = ["DecisionFinalizationStageHandler", "DecisionFinalizationV2StageHandler"]
