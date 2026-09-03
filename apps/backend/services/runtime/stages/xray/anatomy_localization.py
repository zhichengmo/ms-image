"""Anatomy Localization Stage implementation without direct Provider I/O."""

from __future__ import annotations

from typing import Any, Mapping

from apps.backend.core.ai.model_route import AiModelRoute
from apps.backend.core.pipeline import StageResult
from apps.backend.services.runtime.stages.contracts import (
    StageAIRequest,
    StageExecutionContext,
    StageExecutionPlan,
    StageHandlerContractError,
)
from apps.backend.services.runtime.stages.xray.prompt_commands import (
    build_anatomy_localization_ai_request_command,
)


class AnatomyLocalizationStageHandler:
    """Build and consume one batch localization Logical Call."""

    handler_key = "anatomy_localization"
    handler_version = "v1"
    MODEL_ROUTE = AiModelRoute(models=("gpt-5.6-sol",), mode="race")
    PROMPT_KEYS = {"cat": "xray_cat_anatomy_localization", "dog": "xray_dog_anatomy_localization"}

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError(
                "anatomy_localization_stage_invalid"
            )
        prompt_command = build_anatomy_localization_ai_request_command(
            task=context.task, stage=stage
        )
        return StageExecutionPlan(
            ai_request=StageAIRequest(
                prompt_command=prompt_command,
                prompt_key=self.PROMPT_KEYS[prompt_command.safe_context["species"]],
                route=self.MODEL_ROUTE,
            )
        )

    def consume_ai_call(
        self,
        context: StageExecutionContext,
        call_result: Mapping[str, Any],
    ) -> StageResult:
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError(
                "anatomy_localization_stage_invalid"
            )
        parsed = call_result.get("parsed_result_json")
        call_id = call_result.get("call_id")
        accepted = (
            call_result.get("status") == "succeeded"
            and call_result.get("result_disposition") == "accepted"
            and isinstance(call_id, str)
            and bool(call_id)
            and isinstance(parsed, Mapping)
        )
        output: dict[str, Any] = {
            "source_call_id": call_id,
        }
        if accepted:
            output["anatomy_localization_result"] = dict(parsed)
            return StageResult(status="completed", output=output)
        error_code = str(
            call_result.get("error_code") or "anatomy_localization_ai_failed"
        )
        output["error_code"] = error_code
        return StageResult(status="failed", output=output, error_code=error_code)


__all__ = ["AnatomyLocalizationStageHandler"]
