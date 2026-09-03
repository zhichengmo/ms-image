"""批量影像质量复核 Stage；Handler 本身不直接访问 Provider。"""

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
    build_xray_image_quality_ai_request_command,
)


class BatchImageQualityReviewStageHandler:
    """为同一 Study 的冻结影像构造并消费一次批量质量复核 Logical Call。

    Handler 只产生纯 AI 请求意图，持久化、重试、Gateway 和 Provider 传输均由既有
    Worker/AIRequestService 拥有。该 Stage 负责基础影像质量与可读性结果，不负责最终
    疾病诊断，不生成 Report，也不能把工程合同通过解释为医学准确性通过。
    """

    handler_key = "batch_image_quality_review"
    handler_version = "v1"

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        """校验 Stage 身份并返回唯一的一次多图质量复核请求意图。

        此方法不执行网络 I/O；Prompt、冻结影像和调用预算由后续统一请求链解析。
        """
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("xray_image_quality_stage_invalid")
        return StageExecutionPlan(
            ai_request=StageAIRequest(
                prompt_command=build_xray_image_quality_ai_request_command(
                    task=context.task,
                    stage=stage,
                )
            )
        )

    def consume_ai_call(
        self,
        context: StageExecutionContext,
        call_result: Mapping[str, Any],
    ) -> StageResult:
        """把终态 Logical Call 转换为可持久化的 StageResult。

        仅当 Call 已成功、结果被 accepted、``call_id`` 有效且解析结果为对象时完成；
        否则保留 ``source_call_id`` 与错误码并将 Stage 标记为 failed，禁止使用未接受的
        Provider 输出继续下游链路。
        """
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("xray_image_quality_stage_invalid")
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
            output["xray_image_quality_result"] = dict(parsed)
            return StageResult(status="completed", output=output)
        error_code = str(
            call_result.get("error_code") or "xray_image_quality_ai_failed"
        )
        output["error_code"] = error_code
        return StageResult(status="failed", output=output, error_code=error_code)


__all__ = ["BatchImageQualityReviewStageHandler"]
