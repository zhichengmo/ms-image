"""Deterministic XRay Family routing Stage."""

from __future__ import annotations

from apps.backend.core.pipeline import StageResult
from apps.backend.services.runtime.stages.contracts import (
    StageExecutionContext,
    StageHandlerContractError,
)


class XRayFamilyRoutingStageHandler:
    """Return the frozen provider-disabled default route without medical inference."""

    handler_key = "family_routing"
    handler_version = "v1"

    async def execute(self, context: StageExecutionContext) -> StageResult:
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("family_routing_stage_invalid")
        previous_output = (stage.input_json or {}).get("previous_output") or {}
        return StageResult(
            status="completed",
            output={
                "route_signal": "primary_final",
                "source_primary_output_sha256": (stage.input_json or {}).get(
                    "previous_output_sha256"
                ),
                "source_primary_call_id": previous_output.get("source_call_id"),
            },
        )


__all__ = ["XRayFamilyRoutingStageHandler"]
