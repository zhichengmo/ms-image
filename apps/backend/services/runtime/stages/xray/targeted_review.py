"""XRay Targeted review Stage implementation."""

from __future__ import annotations

from typing import Any, Mapping

from apps.backend.core.pipeline import StageResult
from apps.backend.services.runtime.stages.contracts import (
    StageAIRequest,
    StageExecutionContext,
    StageExecutionPlan,
    StageHandlerContractError,
)
from apps.backend.services.runtime.stages.xray.prompt_commands import (
    build_targeted_ai_request_command,
)


class XRayTargetedReviewStageHandler:
    """Build and consume the single permitted Targeted Logical Call."""

    handler_key = "targeted_review"
    handler_version = "v1"

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        task = context.task
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("targeted_review_stage_invalid")
        return StageExecutionPlan(
            ai_request=StageAIRequest(
                prompt_command=build_targeted_ai_request_command(
                    task=task,
                    stage=stage,
                )
            )
        )

    def consume_ai_call(
        self,
        context: StageExecutionContext,
        call_result: Mapping[str, Any],
    ) -> StageResult:
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("targeted_review_stage_invalid")
        parsed = call_result.get("parsed_result_json")
        accepted = (
            call_result.get("status") == "succeeded"
            and call_result.get("result_disposition") == "accepted"
            and isinstance(parsed, Mapping)
        )
        output: dict[str, Any] = {
            "candidate_kind": "targeted",
            "medical_status": "produced" if accepted else "not_produced",
            "source_call_id": call_result.get("call_id"),
            "error_code": call_result.get("error_code"),
            "source_route_sha256": (stage.input_json or {}).get(
                "previous_output_sha256"
            ),
        }
        if accepted:
            output["complete_medical_result"] = dict(parsed)
            return StageResult(status="completed", output=output)
        return StageResult(
            status="failed",
            output=output,
            error_code=str(
                call_result.get("error_code") or "targeted_review_ai_failed"
            ),
        )


class XRayTargetedReviewV2StageHandler(XRayTargetedReviewStageHandler):
    """Version-isolated v2 targeted handler; it does not merge medical results."""

    handler_version = "v2"


__all__ = [
    "XRayTargetedReviewStageHandler",
    "XRayTargetedReviewV2StageHandler",
]
