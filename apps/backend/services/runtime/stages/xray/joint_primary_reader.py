"""XRay Primary reader Stage implementation."""

from __future__ import annotations

from apps.backend.core.pipeline import StageResult
from apps.backend.services.runtime.service.ai_request_service import AIRequestService
from apps.backend.services.runtime.stages.contracts import (
    StageExecutionContext,
    StageHandlerContractError,
)
from apps.backend.services.runtime.stages.xray.prompt_commands import (
    build_primary_ai_request_command,
)


class XRayJointPrimaryReaderStageHandler:
    """Build the XRay Primary command and delegate Call fact ownership to AIRequest."""

    handler_key = "joint_primary_reader"
    handler_version = "v1"

    def __init__(self, ai_request_service: AIRequestService):
        self.ai_request_service = ai_request_service

    async def execute(self, context: StageExecutionContext) -> StageResult:
        task = context.task
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("joint_primary_stage_invalid")
        call = await self.ai_request_service.prepare_provider_disabled_call(
            task_id=stage.task_id,
            stage_checkpoint_id=stage.id,
            prompt_command=build_primary_ai_request_command(task=task, stage=stage),
        )
        return StageResult(
            status="completed",
            output={
                "candidate_kind": "primary",
                "medical_status": "not_produced",
                "source_call_id": call["call_id"],
                "error_code": call["error_code"],
                "manifest_sha256": (stage.input_json or {}).get("manifest_sha256"),
            },
        )


__all__ = ["XRayJointPrimaryReaderStageHandler"]
