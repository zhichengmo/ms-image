"""Technical integrity checks for X-Ray SystemAnalysis results."""

from __future__ import annotations

from typing import Any, Mapping

from apps.backend.core.ai.gateway.contracts import AI_IMAGE_RECEIPT_V2

XRAY_SYSTEM_ANALYSIS_CONTRACT_V1 = "xray-system-analysis.v1"
XRAY_SYSTEM_ANALYSIS_FAMILIES = frozenset(
    {
        "thoracic",
        "abdominal",
        "axial_orthopedic",
        "appendicular_orthopedic",
        "head_neck",
    }
)


class XRaySystemAnalysisContractError(ValueError):
    """Raised when schema-valid SystemAnalysis output breaks frozen lineage."""


def validate_xray_system_analysis_result_contract(
    *,
    result: Mapping[str, Any],
    schema_contract_version: Any,
    image_receipt: Mapping[str, Any],
    expected_species: Any,
) -> dict[str, Any]:
    """Validate identity, frozen image lineage and structural references only."""

    if schema_contract_version != XRAY_SYSTEM_ANALYSIS_CONTRACT_V1:
        raise XRaySystemAnalysisContractError(
            "provider_result_contract_version_unsupported"
        )
    if result.get("contract_version") != XRAY_SYSTEM_ANALYSIS_CONTRACT_V1:
        raise XRaySystemAnalysisContractError(
            "system_analysis_contract_version_invalid"
        )
    if expected_species not in {"cat", "dog"}:
        raise XRaySystemAnalysisContractError(
            "system_analysis_expected_species_invalid"
        )
    if result.get("species") != expected_species:
        raise XRaySystemAnalysisContractError("system_analysis_species_mismatch")

    receipt_images = image_receipt.get("images")
    if (
        image_receipt.get("contract_version") != AI_IMAGE_RECEIPT_V2
        or not isinstance(receipt_images, list)
        or not 2 <= len(receipt_images) <= 5
        or image_receipt.get("image_count") != len(receipt_images)
    ):
        raise XRaySystemAnalysisContractError(
            "system_analysis_source_receipt_invalid"
        )

    receipt_image_ids: set[str] = set()
    receipt_sequences: set[int] = set()
    for item in receipt_images:
        if not isinstance(item, Mapping):
            raise XRaySystemAnalysisContractError(
                "system_analysis_source_receipt_invalid"
            )
        image_id = item.get("image_id")
        sequence_no = item.get("sequence_no")
        if (
            not isinstance(image_id, str)
            or not image_id
            or image_id in receipt_image_ids
            or not isinstance(sequence_no, int)
            or isinstance(sequence_no, bool)
            or sequence_no in receipt_sequences
        ):
            raise XRaySystemAnalysisContractError(
                "system_analysis_source_receipt_invalid"
            )
        receipt_image_ids.add(image_id)
        receipt_sequences.add(sequence_no)

    source_refs = result.get("source_refs")
    if not isinstance(source_refs, list):
        raise XRaySystemAnalysisContractError("system_analysis_result_invalid")
    source_ids: set[str] = set()
    referenced_images: set[str] = set()
    for source_ref in source_refs:
        if (
            not isinstance(source_ref, Mapping)
            or set(source_ref) != {"source_ref_id", "image_id"}
        ):
            raise XRaySystemAnalysisContractError(
                "system_analysis_source_ref_invalid"
            )
        source_ref_id = source_ref.get("source_ref_id")
        image_id = source_ref.get("image_id")
        if (
            not isinstance(source_ref_id, str)
            or not source_ref_id
            or source_ref_id in source_ids
            or not isinstance(image_id, str)
            or not image_id
            or image_id in referenced_images
        ):
            raise XRaySystemAnalysisContractError(
                "system_analysis_source_ref_invalid"
            )
        if image_id not in receipt_image_ids:
            raise XRaySystemAnalysisContractError(
                "system_analysis_source_image_not_sent"
            )
        source_ids.add(source_ref_id)
        referenced_images.add(image_id)
    if referenced_images != receipt_image_ids:
        raise XRaySystemAnalysisContractError(
            "system_analysis_source_coverage_mismatch"
        )

    systems = result.get("systems")
    if not isinstance(systems, list) or len(systems) != len(
        XRAY_SYSTEM_ANALYSIS_FAMILIES
    ):
        raise XRaySystemAnalysisContractError("system_analysis_family_coverage_invalid")
    seen_families: set[str] = set()
    for system in systems:
        if not isinstance(system, Mapping):
            raise XRaySystemAnalysisContractError("system_analysis_result_invalid")
        family_key = system.get("family_key")
        if (
            family_key not in XRAY_SYSTEM_ANALYSIS_FAMILIES
            or family_key in seen_families
        ):
            raise XRaySystemAnalysisContractError(
                "system_analysis_family_coverage_invalid"
            )
        seen_families.add(family_key)
        _validate_source_ids(system.get("source_ref_ids"), source_ids)
        _validate_collection(
            system.get("findings"),
            id_key="finding_id",
            source_ids=source_ids,
        )
        _validate_collection(
            system.get("normal_counterevidence"),
            id_key="evidence_id",
            source_ids=source_ids,
        )
        limitations = _validate_collection(
            system.get("limitations"),
            id_key="limitation_id",
            source_ids=source_ids,
        )
        assessment_status = system.get("assessment_status")
        visible_structures = system.get("visible_structures")
        findings = system.get("findings")
        counterevidence = system.get("normal_counterevidence")
        if not isinstance(visible_structures, list):
            raise XRaySystemAnalysisContractError("system_analysis_result_invalid")
        if assessment_status == "limited" and not limitations:
            raise XRaySystemAnalysisContractError(
                "system_analysis_assessment_status_invalid"
            )
        if assessment_status == "not_assessed" and (
            visible_structures or findings or counterevidence or not limitations
        ):
            raise XRaySystemAnalysisContractError(
                "system_analysis_assessment_status_invalid"
            )
    if seen_families != XRAY_SYSTEM_ANALYSIS_FAMILIES:
        raise XRaySystemAnalysisContractError(
            "system_analysis_family_coverage_invalid"
        )

    _validate_collection(
        result.get("cross_system_patterns"),
        id_key="pattern_id",
        source_ids=source_ids,
        family_key="family_keys",
    )
    _validate_collection(
        result.get("unresolved_conflicts"),
        id_key="conflict_id",
        source_ids=source_ids,
        family_key="affected_family_keys",
    )
    return dict(result)


def _validate_collection(
    value: Any,
    *,
    id_key: str,
    source_ids: set[str],
    family_key: str | None = None,
) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        raise XRaySystemAnalysisContractError("system_analysis_result_invalid")
    seen_ids: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            raise XRaySystemAnalysisContractError("system_analysis_result_invalid")
        item_id = item.get(id_key)
        if not isinstance(item_id, str) or not item_id or item_id in seen_ids:
            raise XRaySystemAnalysisContractError(
                "system_analysis_item_id_invalid"
            )
        seen_ids.add(item_id)
        _validate_source_ids(item.get("source_ref_ids"), source_ids)
        if family_key is not None:
            families = item.get(family_key)
            if (
                not isinstance(families, list)
                or not families
                or len(families) != len(set(families))
                or any(
                    family not in XRAY_SYSTEM_ANALYSIS_FAMILIES
                    for family in families
                )
            ):
                raise XRaySystemAnalysisContractError(
                    "system_analysis_family_reference_invalid"
                )
    return value


def _validate_source_ids(value: Any, source_ids: set[str]) -> None:
    if (
        not isinstance(value, list)
        or not value
        or len(value) != len(set(value))
        or any(source_id not in source_ids for source_id in value)
    ):
        raise XRaySystemAnalysisContractError(
            "system_analysis_cross_reference_invalid"
        )


__all__ = [
    "XRAY_SYSTEM_ANALYSIS_CONTRACT_V1",
    "XRAY_SYSTEM_ANALYSIS_FAMILIES",
    "XRaySystemAnalysisContractError",
    "validate_xray_system_analysis_result_contract",
]
