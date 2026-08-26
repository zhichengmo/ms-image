"""Common frozen-input preparation Stage."""

from __future__ import annotations

from apps.backend.core.pipeline import StageResult
from apps.backend.services.runtime.stages.contracts import (
    StageExecutionContext,
    StageExecutionPlan,
    StageHandlerContractError,
)


class StudyPreparationStageHandler:
    """Validate the frozen Study input and produce a provider-free result."""

    handler_key = "study_preparation"
    handler_version = "v1"

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("study_preparation_stage_invalid")
        input_json = stage.input_json or {}
        study_revision_id = input_json.get("study_revision_id")
        manifest_sha256 = input_json.get("manifest_sha256")
        if not isinstance(study_revision_id, str) or not isinstance(
            manifest_sha256, str
        ):
            raise StageHandlerContractError("study_preparation_input_invalid")
        return StageExecutionPlan(
            completed_result=StageResult(
                status="completed",
                output={
                    "study_revision_id": study_revision_id,
                    "manifest_sha256": manifest_sha256,
                    "status": "prepared",
                    "provider_called": False,
                },
            )
        )


__all__ = ["StudyPreparationStageHandler"]
