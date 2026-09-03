"""Independent zero-image X-Ray ReportGeneration Stage."""

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
    build_report_generation_ai_request_command,
)


class ReportGenerationStageHandler:
    handler_key = "report_generation"
    handler_version = "v1"

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        if context.stage.stage_key != self.handler_key:
            raise StageHandlerContractError("report_generation_stage_invalid")
        return StageExecutionPlan(
            ai_request=StageAIRequest(
                prompt_command=build_report_generation_ai_request_command(
                    task=context.task,
                    stage=context.stage,
                )
            )
        )

    def consume_ai_call(
        self,
        context: StageExecutionContext,
        call_result: Mapping[str, Any],
    ) -> StageResult:
        if context.stage.stage_key != self.handler_key:
            raise StageHandlerContractError("report_generation_stage_invalid")
        parsed = call_result.get("parsed_result_json")
        call_id = call_result.get("call_id")
        accepted = (
            call_result.get("status") == "succeeded"
            and call_result.get("result_disposition") == "accepted"
            and isinstance(call_id, str)
            and bool(call_id)
            and isinstance(parsed, Mapping)
        )
        output: dict[str, Any] = {"source_call_id": call_id}
        if accepted:
            output["medical_status"] = "produced"
            output["report_generation_result"] = dict(parsed)
            output["complete_medical_result"] = dict(
                parsed["final_medical_result"]
            )
            return StageResult(status="completed", output=output)
        error_code = str(
            call_result.get("error_code") or "report_generation_ai_failed"
        )
        output["error_code"] = error_code
        return StageResult(status="failed", output=output, error_code=error_code)


__all__ = ["ReportGenerationStageHandler"]
