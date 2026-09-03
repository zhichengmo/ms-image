"""诊断链通用的冻结输入准备 Stage。"""

from __future__ import annotations

from apps.backend.core.pipeline import StageResult
from apps.backend.services.runtime.stages.contracts import (
    StageExecutionContext,
    StageExecutionPlan,
    StageHandlerContractError,
)


class StudyPreparationStageHandler:
    """校验 Task 创建时冻结的 Study revision 与 manifest 身份。

    这是各 XRay Profile 的通用首个 Stage。它只消费已经持久化在 checkpoint 中的
    ``study_revision_id`` 和 ``manifest_sha256``，不会查询数据库中的 latest revision，
    也不会创建 AI Logical Call。成功结果供后续 Stage 继续携带同一份冻结输入血缘。
    """

    handler_key = "study_preparation"
    handler_version = "v1"

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        """返回不调用 Provider 的已完成计划，输入缺失时按合同失败关闭。

        输出中的 ``provider_called=false`` 只说明本 Stage 没有 AI 调用；它不代表后续
        AI Stage 被禁用，也不产生任何医学判断。
        """
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
