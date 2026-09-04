"""XRay 多图联合主读与主要病例裁决 Stage。"""

from __future__ import annotations

from typing import Any, Mapping

from apps.backend.core.ai.model_route import AiModelRoute
from apps.backend.core.pipeline import XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1, StageResult
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
    """构造并消费 XRay Primary Logical Call，但不拥有网络与持久化 I/O。

    Primary 是产生 ``complete_medical_result`` 的主要 AI 候选层。它消费冻结 Study 上下文
    以及 Profile 提供的上游结果，输出 primary 候选与来源 Call；Handler 不自行调用
    Provider、不查询 latest，也不在 Python 中补写或修复模型医学结论。
    """

    handler_key = "joint_primary_reader"
    handler_version = "v1"
    MODEL_ROUTE = AiModelRoute(models=("gemini-3.8-flash",), mode="race")
    PROMPT_KEYS = {"cat": "xray_cat_primary", "dog": "xray_dog_primary"}
    ADJUDICATION_PROMPT_KEYS = {
        "cat": "xray_cat_primary_adjudication",
        "dog": "xray_dog_primary_adjudication",
    }

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        """校验 Stage 身份并返回唯一的 Primary 多图请求意图。"""
        task = context.task
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("joint_primary_stage_invalid")
        prompt_command = build_primary_ai_request_command(task=task, stage=stage)
        prompt_keys = (
            self.ADJUDICATION_PROMPT_KEYS
            if (task.request_snapshot_json or {}).get("profile_key")
            == XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1
            else self.PROMPT_KEYS
        )
        return StageExecutionPlan(
            ai_request=StageAIRequest(
                prompt_command=prompt_command,
                prompt_key=prompt_keys[prompt_command.safe_context["species"]],
                route=self.MODEL_ROUTE,
                variant=prompt_command.safe_context["species"],
            )
        )

    def consume_ai_call(
        self,
        context: StageExecutionContext,
        call_result: Mapping[str, Any],
    ) -> StageResult:
        """将 accepted Call 转换为 primary 医学候选，并保留完整血缘。

        accepted 时 ``medical_status=produced``，模型对象原样进入
        ``complete_medical_result``。一般失败会使 Stage failed；历史兼容的
        ``provider_disabled`` 只完成一个 ``not_produced`` 结果，不得被解释为 AI 已运行。
        """
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
    """v2 隔离版本；accepted 模型 JSON 继续作为不透明医学结果原样传递。"""

    handler_version = "v2"


__all__ = [
    "XRayJointPrimaryReaderStageHandler",
    "XRayJointPrimaryReaderV2StageHandler",
]
