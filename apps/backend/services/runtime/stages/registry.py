"""Resolve the concrete internal Stage handler for a persisted handler contract."""

from __future__ import annotations

from apps.backend.services.runtime.stages.common import (
    DecisionFinalizationStageHandler,
    DecisionFinalizationV2StageHandler,
    StudyPreparationStageHandler,
)
from apps.backend.services.runtime.stages.contracts import (
    StageHandler,
    StageHandlerContractError,
)
from apps.backend.services.runtime.stages.xray.family_routing import (
    XRayFamilyRoutingStageHandler,
    XRayFamilyRoutingV2StageHandler,
)
from apps.backend.services.runtime.stages.xray.joint_primary_reader import (
    XRayJointPrimaryReaderStageHandler,
    XRayJointPrimaryReaderV2StageHandler,
)
from apps.backend.services.runtime.stages.xray.targeted_review import (
    XRayTargetedReviewStageHandler,
    XRayTargetedReviewV2StageHandler,
)


def resolve_stage_handler(
    *,
    handler_key: str,
    handler_version: str,
) -> StageHandler:
    """Return only an implementation matching the frozen handler key and version."""

    handlers: dict[tuple[str, str], StageHandler] = {
        ("study_preparation", "v1"): StudyPreparationStageHandler(),
        ("joint_primary_reader", "v1"): XRayJointPrimaryReaderStageHandler(),
        ("family_routing", "v1"): XRayFamilyRoutingStageHandler(),
        ("targeted_review", "v1"): XRayTargetedReviewStageHandler(),
        ("decision_finalization", "v1"): DecisionFinalizationStageHandler(),
        ("joint_primary_reader", "v2"): XRayJointPrimaryReaderV2StageHandler(),
        ("family_routing", "v2"): XRayFamilyRoutingV2StageHandler(),
        ("targeted_review", "v2"): XRayTargetedReviewV2StageHandler(),
        ("decision_finalization", "v2"): DecisionFinalizationV2StageHandler(),
    }
    handler = handlers.get((handler_key, handler_version))
    if handler is None:
        raise StageHandlerContractError("stage_handler_not_implemented")
    return handler


__all__ = ["resolve_stage_handler"]
