"""Medical-status ownership at the Runtime persistence boundary."""

from __future__ import annotations

from typing import Any, Mapping


MODEL_MEDICAL_STATUSES = frozenset(
    {"normal", "abnormal", "review_required", "non_diagnostic"}
)
PERSISTED_MEDICAL_STATUSES = MODEL_MEDICAL_STATUSES | {"not_produced"}
RESULT_AVAILABILITIES = frozenset({"produced", "not_produced"})


class MedicalStatusContractError(ValueError):
    """Raised when Stage availability and its medical payload disagree."""


def project_persisted_medical_status(output: Mapping[str, Any]) -> str:
    """Project a v1 Stage availability marker into one persisted status.

    This boundary never infers a medical verdict.  A produced result must own
    one of the four model statuses; the legacy not-produced path must not carry
    a complete result at all.
    """

    availability = output.get("medical_status")
    if (
        not isinstance(availability, str)
        or availability not in RESULT_AVAILABILITIES
    ):
        raise MedicalStatusContractError(
            "finalization_result_availability_invalid"
        )

    result_present = "complete_medical_result" in output
    result = output.get("complete_medical_result")
    if availability == "not_produced":
        if result_present:
            raise MedicalStatusContractError(
                "finalization_result_availability_conflict"
            )
        return "not_produced"

    if not isinstance(result, Mapping):
        raise MedicalStatusContractError("finalization_medical_result_invalid")
    medical_status = result.get("medical_status")
    if (
        not isinstance(medical_status, str)
        or medical_status not in MODEL_MEDICAL_STATUSES
    ):
        raise MedicalStatusContractError("finalization_medical_result_invalid")
    return medical_status


__all__ = [
    "MODEL_MEDICAL_STATUSES",
    "MedicalStatusContractError",
    "PERSISTED_MEDICAL_STATUSES",
    "RESULT_AVAILABILITIES",
    "project_persisted_medical_status",
]
