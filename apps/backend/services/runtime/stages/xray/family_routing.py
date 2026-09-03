"""XRay 确定性 FamilyRouting 条件路由 Stage。"""

from __future__ import annotations

from apps.backend.core.pipeline import StageResult
from apps.backend.services.runtime.stages.contracts import (
    StageExecutionContext,
    StageExecutionPlan,
    StageHandlerContractError,
)


_TARGETED_FOCUS_BY_FAMILY = {
    "thoracic": frozenset(
        {
            "cardiac_silhouette",
            "pulmonary_pattern",
            "lung_pattern",
            "cardiovascular_contour",
            "pleural_mediastinal",
            "thoracic_wall",
        }
    ),
    "abdominal": frozenset(
        {
            "gastrointestinal_obstruction",
            "gi_obstruction",
            "urinary_mineralization",
            "abdominal_mineralization",
            "soft_tissue_mass",
        }
    ),
    "appendicular_orthopedic": frozenset(
        {
            "fracture_luxation",
            "fracture_dislocation",
            "long_bone_joint",
            "alignment",
            "stifle_patella",
        }
    ),
    "axial_orthopedic": frozenset(
        {"fracture_luxation", "alignment", "pelvis_hip"}
    ),
}


class XRayFamilyRoutingStageHandler:
    """在不调用 Provider 的前提下携带 Primary 结果并选择后续路径。

    v1 始终输出 ``primary_final``，将已有的 Primary 状态、医学结果（若存在）和来源 Call 原样向后传递。
    路由 Stage 不读取像素、不生成新医学事实，也不持久化 Report。
    """

    handler_key = "family_routing"
    handler_version = "v1"

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        """生成默认直达 DecisionFinalization 的 provider-free 路由结果。"""
        stage = context.stage
        if stage.stage_key != self.handler_key:
            raise StageHandlerContractError("family_routing_stage_invalid")
        previous_output = (stage.input_json or {}).get("previous_output") or {}
        output = {
            "route_signal": "primary_final",
            "medical_status": previous_output.get("medical_status", "not_produced"),
            "source_primary_output_sha256": (stage.input_json or {}).get(
                "previous_output_sha256"
            ),
            "source_primary_call_id": previous_output.get("source_call_id"),
            "source_call_id": previous_output.get("source_call_id"),
        }
        if isinstance(previous_output.get("complete_medical_result"), dict):
            output["complete_medical_result"] = previous_output[
                "complete_medical_result"
            ]
        return StageExecutionPlan(
            completed_result=StageResult(status="completed", output=output)
        )


class XRayFamilyRoutingV2StageHandler(XRayFamilyRoutingStageHandler):
    """在实验 Profile 中校验并路由一个 Primary 提出的 Targeted 候选。

    候选内容由模型负责；本 Handler 只检查冻结的 family/focus 词表、finding 引用唯一性
    与引用完整性，不看像素、不推断 Family，也不修改 Primary 医学结果。候选缺失或技术
    合同不满足时安全回退为 ``primary_final``；只有合法候选才输出
    ``route_signal=targeted_review``。执行器据此最多动态物化一个 TargetedReview Stage。
    """

    handler_version = "v2"

    async def execute(self, context: StageExecutionContext) -> StageExecutionPlan:
        """验证 Targeted 候选的技术引用；合法时切换条件路由，否则保留 Primary。"""
        primary_final = await super().execute(context)
        completed = primary_final.completed_result
        if completed is None:
            raise StageHandlerContractError("family_routing_result_missing")

        previous_output = (context.stage.input_json or {}).get("previous_output") or {}
        complete_result = previous_output.get("complete_medical_result")
        if not isinstance(complete_result, dict):
            return primary_final
        candidate = complete_result.get("targeted_candidate")
        if not isinstance(candidate, dict):
            return primary_final

        family_key = candidate.get("family_key")
        focus_key = candidate.get("focus_key")
        source_finding_ids = candidate.get("source_finding_ids")
        allowed_focus = _TARGETED_FOCUS_BY_FAMILY.get(family_key)
        if (
            not isinstance(focus_key, str)
            or allowed_focus is None
            or focus_key not in allowed_focus
            or not isinstance(source_finding_ids, list)
            or not source_finding_ids
            or not all(isinstance(item, str) and item for item in source_finding_ids)
            or len(source_finding_ids) != len(set(source_finding_ids))
        ):
            return primary_final

        finding_ids = {
            finding.get("finding_id")
            for finding in complete_result.get("findings") or []
            if isinstance(finding, dict)
            and isinstance(finding.get("finding_id"), str)
        }
        if any(item not in finding_ids for item in source_finding_ids):
            return primary_final

        output = dict(completed.output)
        output.update(
            {
                "route_signal": "targeted_review",
                "selected_family_key": family_key,
                "selected_focus_key": focus_key,
                "selected_strategy_key": None,
                "source_finding_ids": list(source_finding_ids),
                "coverage_proof": complete_result.get("coverage") or {},
                "route_reason_codes": ["primary_targeted_candidate"],
            }
        )
        return StageExecutionPlan(
            completed_result=StageResult(status="completed", output=output)
        )


__all__ = ["XRayFamilyRoutingStageHandler", "XRayFamilyRoutingV2StageHandler"]
