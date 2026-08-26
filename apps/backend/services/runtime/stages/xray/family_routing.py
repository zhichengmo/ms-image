"""Deterministic XRay Family routing Stage."""

from __future__ import annotations

from apps.backend.core.pipeline import StageResult
from apps.backend.services.runtime.stages.contracts import (
    StageExecutionContext,
    StageExecutionPlan,
    StageHandlerContractError,
)


class XRayFamilyRoutingStageHandler:
    """Route deterministically while carrying the accepted Primary result forward."""

    handler_key = "family_routing"
    handler_version = "v1"

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("family_routing_stage_invalid")
        previous_output = (stage.input_json or {}).get("previous_output") or {}
        output = {
            "route_signal": "primary_final",
            "medical_status": previous_output.get("medical_status", "not_produced"),
            "source_primary_output_sha256": (stage.input_json or {}).get(
                "previous_output_sha256"
            ),
            "source_primary_call_id": previous_output.get("source_call_id"),
            "source_call_id": previous_output.get("source_call_id"),
        }
        if isinstance(previous_output.get("complete_medical_result"), dict):
            output["complete_medical_result"] = previous_output[
                "complete_medical_result"
            ]
        return StageExecutionPlan(
            completed_result=StageResult(status="completed", output=output)
        )


__all__ = ["XRayFamilyRoutingStageHandler"]
