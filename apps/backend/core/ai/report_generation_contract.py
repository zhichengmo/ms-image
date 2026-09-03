"""Truth-preserving validation for the independent X-Ray report stage."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

XRAY_FINAL_REPORT_CONTRACT_V1 = "xray-final-report.v1"


class XRayReportGenerationContractError(ValueError):
    """Raised when a schema-valid report rewrites frozen medical truth."""


def validate_xray_report_generation_result_contract(
    *,
    result: Mapping[str, Any],
    schema_contract_version: Any,
    expected_source_result_sha256: Any,
    expected_final_medical_result: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        schema_contract_version != XRAY_FINAL_REPORT_CONTRACT_V1
        or result.get("result_schema_version") != XRAY_FINAL_REPORT_CONTRACT_V1
    ):
        raise XRayReportGenerationContractError(
            "report_generation_contract_version_invalid"
        )
    if (
        not isinstance(expected_source_result_sha256, str)
        or len(expected_source_result_sha256) != 64
        or result.get("source_result_sha256")
        != expected_source_result_sha256
    ):
        raise XRayReportGenerationContractError(
            "report_generation_source_result_mismatch"
        )
    expected = deepcopy(dict(expected_final_medical_result))
    if result.get("final_medical_result") != expected:
        raise XRayReportGenerationContractError(
            "report_generation_medical_result_rewritten"
        )
    if result.get("medical_status") != expected.get("medical_status"):
        raise XRayReportGenerationContractError(
            "report_generation_medical_status_mismatch"
        )
    return deepcopy(dict(result))


__all__ = [
    "XRAY_FINAL_REPORT_CONTRACT_V1",
    "XRayReportGenerationContractError",
    "validate_xray_report_generation_result_contract",
]
