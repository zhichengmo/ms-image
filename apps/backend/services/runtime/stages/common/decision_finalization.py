"""诊断链通用的最终结果选择 Stage。"""

from __future__ import annotations

from apps.backend.core.pipeline import StageResult
from apps.backend.services.runtime.stages.contracts import (
    StageExecutionContext,
    StageExecutionPlan,
    StageHandlerContractError,
)


class DecisionFinalizationStageHandler:
    """从 Primary 或 Targeted 的既有输出中选择最终持久化候选。

    本 Handler 是确定性编排层，不创建 AI Logical Call。它只识别上游候选类型、转抄
    医学状态与血缘，并在存在 ``complete_medical_result`` 时原样携带该对象。执行器在
    本 Stage 完成后调用 ``ReportService.finalize``；当前没有独立 ReportGeneration AI
    Stage，因此这里不能新增、删减或重写医学事实。
    """

    handler_key = "decision_finalization"
    handler_version = "v1"

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        """确定最终 owner 并生成可持久化的、无 Provider 副作用的 Stage 输出。

        ``selected_owner`` 仅依据上游 ``candidate_kind`` 选择 ``primary`` 或
        ``targeted``；``provider_called`` 是对上游是否产出医学结果的事实标记，不表示
        本 Stage 自己调用过 Provider。stage key 不匹配时立即抛出合同错误。
        """
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("decision_finalization_stage_invalid")
        previous_output = (stage.input_json or {}).get("previous_output") or {}
        output = {
            "medical_status": previous_output.get("medical_status", "not_produced"),
            "selected_owner": (
                "targeted"
                if previous_output.get("candidate_kind") == "targeted"
                else "primary"
            ),
            "source_stage_id": (stage.input_json or {}).get("previous_stage_id"),
            "source_call_id": previous_output.get("source_call_id"),
            "provider_called": previous_output.get("medical_status") == "produced",
        }
        if isinstance(previous_output.get("complete_medical_result"), dict):
            output["complete_medical_result"] = previous_output[
                "complete_medical_result"
            ]
        return StageExecutionPlan(
            completed_result=StageResult(status="completed", output=output)
        )


class DecisionFinalizationV2StageHandler(DecisionFinalizationStageHandler):
    """v2 隔离版本；继续原样保留模型结果，不增加二次诊断或报告生成。"""

    handler_version = "v2"


__all__ = ["DecisionFinalizationStageHandler", "DecisionFinalizationV2StageHandler"]
