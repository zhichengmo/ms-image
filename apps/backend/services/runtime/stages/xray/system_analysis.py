"""Study 级全系统分析 Stage；Handler 本身不直接访问 Provider。"""

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
    build_system_analysis_ai_request_command,
)


class SystemAnalysisStageHandler:
    """构造并消费一次覆盖冻结 Study 影像的全系统分析 Logical Call。

    该 Stage 面向跨系统、跨影像的结构化分析，但不直接生成最终 Report。Handler 只负责
    请求意图与终态 Call 到 StageResult 的转换；图片组装、Provider I/O、Schema 和动态
    lineage 校验由统一 AI 请求链负责。
    """

    handler_key = "system_analysis"
    handler_version = "v1"
    MODEL_ROUTE = AiModelRoute(models=("gpt-5.6-sol",), mode="race")
    PROMPT_KEYS = {"cat": "xray_cat_system_analysis", "dog": "xray_dog_system_analysis"}

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        """校验 Stage 身份并返回唯一的多图 SystemAnalysis 请求意图。"""
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("system_analysis_stage_invalid")
        prompt_command = build_system_analysis_ai_request_command(
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
        """只接受已成功且 disposition 为 accepted 的结构化分析结果。

        accepted 时保留 ``source_call_id`` 并写入 ``system_analysis_result``；其他情况
        使用请求链给出的错误码失败关闭，不生成 Python 推断或兜底医学结果。
        """
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("system_analysis_stage_invalid")
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
            output["system_analysis_result"] = dict(parsed)
            return StageResult(status="completed", output=output)
        error_code = str(
            call_result.get("error_code") or "system_analysis_ai_failed"
        )
        output["error_code"] = error_code
        return StageResult(status="failed", output=output, error_code=error_code)


__all__ = ["SystemAnalysisStageHandler"]
