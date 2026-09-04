"""XRay 条件性专项复核 Stage。"""

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
    build_targeted_ai_request_command,
)


class XRayTargetedReviewStageHandler:
    """构造并消费条件路由允许的唯一一次 TargetedReview Logical Call。

    本 Stage 不是固定必经节点；仅当 FamilyRouting 输出 ``targeted_review`` 时，由执行器
    按编译合同动态物化，且 ``max_instances=1``。它针对 Primary 指定的 family/focus 做
    专项复核，Handler 不直接访问 Provider，也不自行合并多个医学结果。
    """

    handler_key = "targeted_review"
    handler_version = "v1"
    MODEL_ROUTE = AiModelRoute(models=("gemini-3.8-flash",), mode="race")
    PROMPT_KEYS = {"cat": "xray_cat_targeted_review", "dog": "xray_dog_targeted_review"}

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        """校验 Stage 身份并返回一次 TargetedReview 请求意图。"""
        task = context.task
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("targeted_review_stage_invalid")
        prompt_command = build_targeted_ai_request_command(task=task, stage=stage)
        return StageExecutionPlan(
            ai_request=StageAIRequest(
                prompt_command=prompt_command,
                prompt_key=self.PROMPT_KEYS[prompt_command.safe_context["species"]],
                route=self.MODEL_ROUTE,
                variant=prompt_command.safe_context["species"],
            )
        )

    def consume_ai_call(
        self,
        context: StageExecutionContext,
        call_result: Mapping[str, Any],
    ) -> StageResult:
        """把 accepted Call 转换为 targeted 医学候选，失败时终止该 Stage。

        成功结果保留来源 Call 与 FamilyRouting 输出哈希，并将模型对象原样放入
        ``complete_medical_result``；未 accepted 的结果不会覆盖 Primary，也不会由
        Python 生成兜底专项结论。
        """
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("targeted_review_stage_invalid")
        parsed = call_result.get("parsed_result_json")
        accepted = (
            call_result.get("status") == "succeeded"
            and call_result.get("result_disposition") == "accepted"
            and isinstance(parsed, Mapping)
        )
        output: dict[str, Any] = {
            "candidate_kind": "targeted",
            "medical_status": "produced" if accepted else "not_produced",
            "source_call_id": call_result.get("call_id"),
            "error_code": call_result.get("error_code"),
            "source_route_sha256": (stage.input_json or {}).get(
                "previous_output_sha256"
            ),
        }
        snapshot = context.task.request_snapshot_json or {}
        bindings = snapshot.get("stage_ai_config_bindings") or {}
        binding = (
            bindings.get("targeted_review") if isinstance(bindings, Mapping) else None
        )
        dedicated_prompt = snapshot.get("runtime_config_source") == "code" or (
            binding.get("prompt_key") if isinstance(binding, Mapping) else None
        ) in {"xray_cat_targeted_review", "xray_dog_targeted_review"}
        if (
            accepted
            and dedicated_prompt
            and parsed.get("targeted_candidate") is not None
        ):
            output["medical_status"] = "not_produced"
            output["error_code"] = "targeted_review_recursive_candidate_forbidden"
            return StageResult(
                status="failed",
                output=output,
                error_code="targeted_review_recursive_candidate_forbidden",
            )
        if accepted:
            output["complete_medical_result"] = dict(parsed)
            return StageResult(status="completed", output=output)
        return StageResult(
            status="failed",
            output=output,
            error_code=str(
                call_result.get("error_code") or "targeted_review_ai_failed"
            ),
        )


class XRayTargetedReviewV2StageHandler(XRayTargetedReviewStageHandler):
    """v2 隔离版本；仍不在 Handler 内合并或改写 Primary/Targeted 医学结果。"""

    handler_version = "v2"


__all__ = [
    "XRayTargetedReviewStageHandler",
    "XRayTargetedReviewV2StageHandler",
]
