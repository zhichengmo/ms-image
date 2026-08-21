"""Resolve the concrete internal Stage handler for a persisted handler contract."""

from __future__ import annotations

from apps.backend.services.runtime.service.ai_request_service import AIRequestService
from apps.backend.services.runtime.stages.common import (
    DecisionFinalizationStageHandler,
    StudyPreparationStageHandler,
)
from apps.backend.services.runtime.stages.contracts import (
    StageHandler,
    StageHandlerContractError,
)
from apps.backend.services.runtime.stages.xray.family_routing import (
    XRayFamilyRoutingStageHandler,
)
from apps.backend.services.runtime.stages.xray.joint_primary_reader import (
    XRayJointPrimaryReaderStageHandler,
)
from apps.backend.services.runtime.stages.xray.targeted_review import (
    XRayTargetedReviewStageHandler,
)


def resolve_stage_handler(
    *,
    handler_key: str,
    handler_version: str,
    ai_request_service: AIRequestService,
) -> StageHandler:
    """Return only an implementation matching the frozen handler key and version."""

    handlers: dict[tuple[str, str], StageHandler] = {
        ("study_preparation", "v1"): StudyPreparationStageHandler(),
        ("joint_primary_reader", "v1"): XRayJointPrimaryReaderStageHandler(
            ai_request_service
        ),
        ("family_routing", "v1"): XRayFamilyRoutingStageHandler(),
        ("targeted_review", "v1"): XRayTargetedReviewStageHandler(
            ai_request_service
        ),
        ("decision_finalization", "v1"): DecisionFinalizationStageHandler(),
    }
    handler = handlers.get((handler_key, handler_version))
    if handler is None:
        raise StageHandlerContractError("stage_handler_not_implemented")
    return handler


__all__ = ["resolve_stage_handler"]
