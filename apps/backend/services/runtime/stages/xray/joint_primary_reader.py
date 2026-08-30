"""XRay Primary reader Stage implementation."""

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
    build_primary_ai_request_command,
)


class XRayJointPrimaryReaderStageHandler:
    """Build and consume the XRay Primary Logical Call without owning I/O."""

    handler_key = "joint_primary_reader"
    handler_version = "v1"

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        task = context.task
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("joint_primary_stage_invalid")
        return StageExecutionPlan(
            ai_request=StageAIRequest(
                prompt_command=build_primary_ai_request_command(
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
            raise StageHandlerContractError("joint_primary_stage_invalid")
        parsed = call_result.get("parsed_result_json")
        accepted = (
            call_result.get("status") == "succeeded"
            and call_result.get("result_disposition") == "accepted"
            and isinstance(parsed, Mapping)
        )
        output: dict[str, Any] = {
            "candidate_kind": "primary",
            "medical_status": "produced" if accepted else "not_produced",
            "source_call_id": call_result.get("call_id"),
            "error_code": call_result.get("error_code"),
            "manifest_sha256": (stage.input_json or {}).get("manifest_sha256"),
        }
        if accepted:
            output["complete_medical_result"] = dict(parsed)
            return StageResult(status="completed", output=output)
        error_code = str(call_result.get("error_code") or "primary_ai_failed")
        if error_code == "provider_disabled":
            return StageResult(status="completed", output=output)
        return StageResult(status="failed", output=output, error_code=error_code)


class XRayJointPrimaryReaderV2StageHandler(XRayJointPrimaryReaderStageHandler):
    """Version-isolated v2 result handler; accepted model JSON remains opaque."""

    handler_version = "v2"


__all__ = [
    "XRayJointPrimaryReaderStageHandler",
    "XRayJointPrimaryReaderV2StageHandler",
]
