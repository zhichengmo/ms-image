"""Shared engineering contract for X-Ray diagnostic image inputs."""

from __future__ import annotations

from typing import Any

from apps.backend.core.pipeline import (
    XRAY_ANATOMY_LOCALIZATION_PROFILE_V1,
    XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1,
    XRAY_DIAGNOSE_STUDY_SCREENING_PROFILE_V1,
    XRAY_IMAGE_QUALITY_PROFILE_V1,
    XRAY_STUDY_SCREENING_PROFILE_V1,
    XRAY_STUDY_SCREENING_PROFILE_V2,
    XRAY_SYSTEM_ANALYSIS_PROFILE_V1,
)


XRAY_MODALITY_TYPE = "xray"
XRAY_STUDY_MIN_IMAGE_COUNT = 2
XRAY_STUDY_MAX_IMAGE_COUNT = 5
XRAY_SERIES_MIN_IMAGE_COUNT = 1
XRAY_SERIES_MAX_IMAGE_COUNT = 5
XRAY_DIAGNOSTIC_IMAGE_ROLE = "original"
XRAY_DIAGNOSTIC_IMAGE_KIND = "instance"
XRAY_OCCUPYING_IMAGE_STATUSES = frozenset({"uploading", "validating", "ready"})
XRAY_RUNTIME_PROFILES = frozenset(
    {
        "xray_primary_v2",
        "xray_targeted_review_v2",
        XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1,
        XRAY_DIAGNOSE_STUDY_SCREENING_PROFILE_V1,
    }
)
XRAY_ANATOMY_LOCALIZATION_TASK_TYPE = "anatomy_localization"
XRAY_IMAGE_QUALITY_TASK_TYPE = "xray_quality_control"
XRAY_STUDY_SCREENING_TASK_TYPE = "xray_study_screening"
XRAY_SYSTEM_ANALYSIS_TASK_TYPE = "xray_system_analysis"


def is_xray_modality(value: Any) -> bool:
    return isinstance(value, str) and value.strip().casefold() == XRAY_MODALITY_TYPE


def is_xray_diagnostic_image(value: Any) -> bool:
    return (
        getattr(value, "image_role", None) == XRAY_DIAGNOSTIC_IMAGE_ROLE
        and getattr(value, "image_kind", None) == XRAY_DIAGNOSTIC_IMAGE_KIND
    )


def is_xray_diagnostic_image_values(*, image_role: str, image_kind: str) -> bool:
    return (
        image_role == XRAY_DIAGNOSTIC_IMAGE_ROLE
        and image_kind == XRAY_DIAGNOSTIC_IMAGE_KIND
    )


def require_xray_study_image_count(value: Any) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not XRAY_STUDY_MIN_IMAGE_COUNT
        <= value
        <= XRAY_STUDY_MAX_IMAGE_COUNT
    ):
        raise ValueError("xray_study_image_count_out_of_range")
    return value


def require_xray_series_image_count(value: Any) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or not XRAY_SERIES_MIN_IMAGE_COUNT
        <= value
        <= XRAY_SERIES_MAX_IMAGE_COUNT
    ):
        raise ValueError("xray_series_image_count_out_of_range")
    return value


def requires_xray_runtime_image_contract(
    *, modality_type: Any, task_type: Any, profile_key: Any
) -> bool:
    if not is_xray_modality(modality_type):
        return False
    return (
        task_type == "diagnose" and profile_key in XRAY_RUNTIME_PROFILES
    ) or (
        task_type == XRAY_ANATOMY_LOCALIZATION_TASK_TYPE
        and profile_key == XRAY_ANATOMY_LOCALIZATION_PROFILE_V1
    ) or (
        task_type == XRAY_IMAGE_QUALITY_TASK_TYPE
        and profile_key == XRAY_IMAGE_QUALITY_PROFILE_V1
    ) or (
        task_type == XRAY_STUDY_SCREENING_TASK_TYPE
        and profile_key == XRAY_STUDY_SCREENING_PROFILE_V2
    ) or (
        task_type == XRAY_SYSTEM_ANALYSIS_TASK_TYPE
        and profile_key == XRAY_SYSTEM_ANALYSIS_PROFILE_V1
    )


def requires_exact_xray_five_image_config_contract(
    *, modality_type: Any, task_type: Any, profile_key: Any
) -> bool:
    """Return whether a Config must freeze the exact five-image budget."""

    if not is_xray_modality(modality_type):
        return False
    return (
        task_type == "diagnose"
        and profile_key
        in {
            "xray_primary_v2",
            XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1,
            XRAY_DIAGNOSE_STUDY_SCREENING_PROFILE_V1,
            XRAY_STUDY_SCREENING_PROFILE_V1,
            XRAY_STUDY_SCREENING_PROFILE_V2,
        }
    ) or (
        task_type == XRAY_ANATOMY_LOCALIZATION_TASK_TYPE
        and profile_key == XRAY_ANATOMY_LOCALIZATION_PROFILE_V1
    ) or (
        task_type == XRAY_IMAGE_QUALITY_TASK_TYPE
        and profile_key == XRAY_IMAGE_QUALITY_PROFILE_V1
    ) or (
        task_type == XRAY_STUDY_SCREENING_TASK_TYPE
        and profile_key == XRAY_STUDY_SCREENING_PROFILE_V2
    ) or (
        task_type == XRAY_SYSTEM_ANALYSIS_TASK_TYPE
        and profile_key == XRAY_SYSTEM_ANALYSIS_PROFILE_V1
    )


__all__ = [
    "XRAY_DIAGNOSTIC_IMAGE_KIND",
    "XRAY_DIAGNOSTIC_IMAGE_ROLE",
    "XRAY_ANATOMY_LOCALIZATION_PROFILE_V1",
    "XRAY_ANATOMY_LOCALIZATION_TASK_TYPE",
    "XRAY_DIAGNOSE_FULL_CHAIN_PROFILE_V1",
    "XRAY_DIAGNOSE_STUDY_SCREENING_PROFILE_V1",
    "XRAY_IMAGE_QUALITY_PROFILE_V1",
    "XRAY_IMAGE_QUALITY_TASK_TYPE",
    "XRAY_MODALITY_TYPE",
    "XRAY_OCCUPYING_IMAGE_STATUSES",
    "XRAY_RUNTIME_PROFILES",
    "XRAY_SERIES_MAX_IMAGE_COUNT",
    "XRAY_SERIES_MIN_IMAGE_COUNT",
    "XRAY_STUDY_MAX_IMAGE_COUNT",
    "XRAY_STUDY_MIN_IMAGE_COUNT",
    "XRAY_STUDY_SCREENING_PROFILE_V1",
    "XRAY_STUDY_SCREENING_PROFILE_V2",
    "XRAY_STUDY_SCREENING_TASK_TYPE",
    "XRAY_SYSTEM_ANALYSIS_PROFILE_V1",
    "XRAY_SYSTEM_ANALYSIS_TASK_TYPE",
    "is_xray_diagnostic_image",
    "is_xray_diagnostic_image_values",
    "is_xray_modality",
    "require_xray_series_image_count",
    "require_xray_study_image_count",
    "requires_xray_runtime_image_contract",
    "requires_exact_xray_five_image_config_contract",
]
