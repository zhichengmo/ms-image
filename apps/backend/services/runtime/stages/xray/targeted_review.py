"""XRay Targeted review Stage implementation."""

from __future__ import annotations

from apps.backend.core.pipeline import StageResult
from apps.backend.services.runtime.service.ai_request_service import AIRequestService
from apps.backend.services.runtime.stages.contracts import (
    StageExecutionContext,
    StageHandlerContractError,
)
from apps.backend.services.runtime.stages.xray.prompt_commands import (
    build_targeted_ai_request_command,
)


class XRayTargetedReviewStageHandler:
    """Fail closed when the single permitted Targeted call cannot run."""

    handler_key = "targeted_review"
    handler_version = "v1"

    def __init__(self, ai_request_service: AIRequestService):
        self.ai_request_service = ai_request_service

    async def execute(self, context: StageExecutionContext) -> StageResult:
        task = context.task
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("targeted_review_stage_invalid")
        call = await self.ai_request_service.prepare_provider_disabled_call(
            task_id=stage.task_id,
            stage_checkpoint_id=stage.id,
            prompt_command=build_targeted_ai_request_command(task=task, stage=stage),
        )
        output = {
            "candidate_kind": "targeted",
            "medical_status": "not_produced",
            "source_call_id": call["call_id"],
            "error_code": call["error_code"],
            "source_route_sha256": (stage.input_json or {}).get(
                "previous_output_sha256"
            ),
        }
        if output["error_code"]:
            return StageResult(
                status="failed",
                output=output,
                error_code="targeted_review_provider_disabled",
            )
        return StageResult(status="completed", output=output)


__all__ = ["XRayTargetedReviewStageHandler"]
