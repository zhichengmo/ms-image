"""Study 级快速筛查 Stage；Handler 本身不直接访问 Provider。"""

from __future__ import annotations

from typing import Any, Mapping

from apps.backend.core.ai.model_route import AiModelRoute
from apps.backend.core.ai.study_screening_contract import (
    XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2,
    XRayStudyScreeningContractError,
    canonicalize_xray_study_screening_result,
)
from apps.backend.core.pipeline import StageResult
from apps.backend.services.runtime.stages.contracts import (
    StageAIRequest,
    StageExecutionContext,
    StageExecutionPlan,
    StageHandlerContractError,
)
from apps.backend.services.runtime.stages.xray.prompt_commands import (
    build_study_screening_ai_request_command,
)


class StudyScreeningStageHandler:
    """构造并消费一次覆盖冻结 Study 影像的快速筛查 Logical Call。

    StudyScreening 用于输出 Study 级筛查结果和后续判读线索，不是最终诊断与 Report。
    Handler 只声明请求意图、消费已持久化的 Call 事实；Gateway、Provider 调用和通用
    Schema 校验仍由统一执行链负责。
    """

    handler_key = "study_screening"
    handler_version = "v1"
    MODEL_ROUTE = AiModelRoute(models=("gpt-5.6-sol",), mode="race")
    PROMPT_KEYS = {"cat": "xray_cat_study_screening", "dog": "xray_dog_study_screening"}

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        """校验 Stage 身份并返回唯一的多图 StudyScreening 请求意图。"""
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("study_screening_stage_invalid")
        prompt_command = build_study_screening_ai_request_command(
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
        """消费 v1 Call；仅 accepted 的对象结果能够推进 Stage。

        v1 保留历史冻结行为，直接持久化已经被请求层接受的 parsed result。任何终态失败
        或缺少有效 ``call_id`` 的结果均失败关闭，不会生成筛查兜底结论。
        """
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("study_screening_stage_invalid")
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
            output["study_screening_result"] = dict(parsed)
            return StageResult(status="completed", output=output)
        error_code = str(call_result.get("error_code") or "study_screening_ai_failed")
        output["error_code"] = error_code
        return StageResult(status="failed", output=output, error_code=error_code)


class StudyScreeningV2StageHandler(StudyScreeningStageHandler):
    """v2 双边界实现：用冻结 image receipt 补齐并校验 Provider 图像锚点。

    Provider 原始 v2 结果仍保留在 AICall 审计边界；本 Handler 只生成供 Stage 下游使用的
    canonical v2 结果。canonicalizer 只能补充技术 lineage，不能修改模型的医学字段。
    """

    handler_version = "v2"

    def consume_ai_call(
        self,
        context: StageExecutionContext,
        call_result: Mapping[str, Any],
    ) -> StageResult:
        """消费 v2 Call，并在持久化前执行 species 与逐图 receipt 血缘收敛。

        accepted 只是进入 canonicalization 的必要条件；source ref 唯一性、全部 receipt
        影像覆盖或 species 不一致时仍会以合同错误将 Stage 标记为 failed。失败时不会
        改写 AICall raw result，也不会绕过 lineage 继续 Primary。
        """
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("study_screening_stage_invalid")
        parsed = call_result.get("parsed_result_json")
        image_receipt = call_result.get("image_receipt_json")
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
            snapshot = getattr(context.task, "request_snapshot_json", None)
            expected_species = (
                snapshot.get("species") if isinstance(snapshot, Mapping) else None
            )
            try:
                canonical = canonicalize_xray_study_screening_result(
                    provider_result=parsed,
                    schema_contract_version=(
                        XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2
                    ),
                    image_receipt=image_receipt,
                    expected_species=expected_species,
                )
            except XRayStudyScreeningContractError as exc:
                error_code = str(exc)
                output["error_code"] = error_code
                return StageResult(
                    status="failed",
                    output=output,
                    error_code=error_code,
                )
            output["study_screening_result"] = canonical
            return StageResult(status="completed", output=output)
        error_code = str(
            call_result.get("error_code") or "study_screening_ai_failed"
        )
        output["error_code"] = error_code
        return StageResult(status="failed", output=output, error_code=error_code)


__all__ = [
    "StudyScreeningStageHandler",
    "StudyScreeningV2StageHandler",
]
