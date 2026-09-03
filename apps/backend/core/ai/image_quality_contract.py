"""Technical integrity checks for X-Ray batch image quality review."""

from __future__ import annotations

from typing import Any, Mapping

from apps.backend.core.ai.config_contract import TASK_REQUEST_SNAPSHOT_V3
from apps.backend.core.ai.gateway.contracts import AI_IMAGE_RECEIPT_V2
from apps.backend.core.imaging.manifest import (
    ManifestContractError,
    validate_frozen_study_series,
)

XRAY_IMAGE_QUALITY_CONTRACT_V1 = "xray-image-quality.v1"
XRAY_IMAGE_QUALITY_RESULT_STATUSES = frozenset(
    {"complete", "partial", "unavailable"}
)
XRAY_IMAGE_QUALITY_SPECIES_CONSISTENCY = frozenset(
    {"consistent", "inconsistent", "indeterminate"}
)
XRAY_IMAGE_QUALITY_BODY_PARTS = frozenset(
    {
        "head_neck",
        "thorax",
        "abdomen",
        "axial_skeleton",
        "appendicular_skeleton",
        "other",
        "indeterminate",
    }
)
XRAY_IMAGE_QUALITY_PROJECTIONS = frozenset(
    {
        "right_lateral",
        "left_lateral",
        "lateral_indeterminate",
        "ventrodorsal",
        "dorsoventral",
        "craniocaudal",
        "caudocranial",
        "mediolateral",
        "lateromedial",
        "oblique",
        "open_mouth",
        "other",
        "indeterminate",
    }
)
XRAY_IMAGE_QUALITY_PROJECTION_CONSISTENCY = frozenset(
    {"consistent", "inconsistent", "indeterminate"}
)
_XRAY_DECLARED_PROJECTION_ALIASES = {
    "vd": "ventrodorsal",
    "dv": "dorsoventral",
    "ml": "mediolateral",
    "lm": "lateromedial",
    "cc": "craniocaudal",
    "cd": "caudocranial",
}
_XRAY_LATERAL_PROJECTIONS = frozenset(
    {"right_lateral", "left_lateral", "lateral_indeterminate"}
)
XRAY_IMAGE_QUALITY_STATUSES = frozenset(
    {"diagnostic", "limited", "non_diagnostic"}
)
XRAY_IMAGE_QUALITY_ISSUE_CODES = frozenset(
    {
        "positioning",
        "rotation",
        "anatomy_cutoff",
        "underexposure",
        "overexposure",
        "low_contrast",
        "motion",
        "artifact",
        "marker_missing",
        "projection_indeterminate",
        "non_xray_or_unsupported",
    }
)


class XRayImageQualityContractError(ValueError):
    """Raised when a schema-valid quality result breaks its frozen contract."""


def validate_xray_image_quality_receipt_against_snapshot(
    *,
    snapshot: Mapping[str, Any],
    image_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Reproduce the v3 image receipt from immutable Task image facts."""

    if snapshot.get("snapshot_contract_version") != TASK_REQUEST_SNAPSHOT_V3:
        raise XRayImageQualityContractError("xray_image_quality_snapshot_v3_required")
    try:
        frozen_series = validate_frozen_study_series(
            snapshot.get("series"),
            resolved_manifest_sha256=snapshot.get("resolved_manifest_sha256"),
        )
    except ManifestContractError as exc:
        raise XRayImageQualityContractError(
            "xray_image_quality_snapshot_lineage_invalid"
        ) from exc

    expected_images: list[dict[str, Any]] = []
    for series in frozen_series:
        for item in series["ordered_images"]:
            expected_images.append(
                {
                    "sequence_no": len(expected_images) + 1,
                    "series_id": series["series_id"],
                    "series_manifest_sha256": series["manifest_sha256"],
                    "series_sequence_no": item["sequence_no"],
                    "image_id": item["image_id"],
                    "logical_image_key": item["logical_image_key"],
                    "image_version_no": item["image_version_no"],
                    "projection": item["projection"],
                    "projection_provenance": item["projection_provenance"],
                    "sha256": item["sha256"],
                    "size_bytes": item["size_bytes"],
                    "mime_type": item["content_type"],
                }
            )
    if (
        image_receipt.get("contract_version") != AI_IMAGE_RECEIPT_V2
        or not 2 <= len(expected_images) <= 5
        or image_receipt.get("image_count") != len(expected_images)
        or image_receipt.get("images") != expected_images
    ):
        raise XRayImageQualityContractError(
            "xray_image_quality_snapshot_receipt_mismatch"
        )
    return dict(image_receipt)


def _expected_projection_consistency(
    *, declared_projection: Any, observed_projection: str
) -> str:
    declared = (
        declared_projection.strip().casefold()
        if isinstance(declared_projection, str)
        else ""
    )
    declared = _XRAY_DECLARED_PROJECTION_ALIASES.get(declared, declared)
    if (
        observed_projection in {"indeterminate", "lateral_indeterminate"}
        or declared == "indeterminate"
    ):
        return "indeterminate"
    if declared == "lateral":
        return (
            "consistent"
            if observed_projection in _XRAY_LATERAL_PROJECTIONS
            else "inconsistent"
        )
    if declared not in XRAY_IMAGE_QUALITY_PROJECTIONS:
        return "indeterminate"
    return "consistent" if declared == observed_projection else "inconsistent"


def validate_xray_image_quality_result_contract(
    *,
    result: Mapping[str, Any],
    schema_contract_version: Any,
    image_receipt: Mapping[str, Any],
    expected_species: Any,
) -> dict[str, Any]:
    """Validate exact image coverage and technical cross-field invariants."""

    if schema_contract_version != XRAY_IMAGE_QUALITY_CONTRACT_V1:
        raise XRayImageQualityContractError(
            "provider_result_contract_version_unsupported"
        )
    if expected_species not in {"cat", "dog"}:
        raise XRayImageQualityContractError(
            "xray_image_quality_expected_species_invalid"
        )
    if (
        result.get("contract_version") != XRAY_IMAGE_QUALITY_CONTRACT_V1
        or result.get("species") != expected_species
    ):
        raise XRayImageQualityContractError(
            "xray_image_quality_result_identity_invalid"
        )

    receipt_images = image_receipt.get("images")
    result_images = result.get("images")
    if (
        image_receipt.get("contract_version") != AI_IMAGE_RECEIPT_V2
        or not isinstance(receipt_images, list)
        or image_receipt.get("image_count") != len(receipt_images)
        or not 2 <= len(receipt_images) <= 5
        or not isinstance(result_images, list)
        or len(result_images) != len(receipt_images)
    ):
        raise XRayImageQualityContractError(
            "xray_image_quality_source_receipt_invalid"
        )

    valid_count = 0
    image_ids_seen: set[str] = set()
    for expected_sequence, (receipt, image_result) in enumerate(
        zip(receipt_images, result_images, strict=True), start=1
    ):
        if not isinstance(receipt, Mapping) or not isinstance(image_result, Mapping):
            raise XRayImageQualityContractError(
                "xray_image_quality_image_contract_invalid"
            )
        image_id = receipt.get("image_id")
        if (
            not isinstance(image_id, str)
            or not image_id
            or receipt.get("sequence_no") != expected_sequence
            or image_result.get("image_id") != image_id
            or image_result.get("sequence_no") != expected_sequence
            or image_id in image_ids_seen
        ):
            raise XRayImageQualityContractError(
                f"xray_image_quality_image_{expected_sequence}_lineage_mismatch"
            )
        image_ids_seen.add(image_id)

        is_valid_xray = image_result.get("is_valid_xray")
        species_consistency = image_result.get("species_consistency")
        primary_body_part = image_result.get("primary_body_part")
        visible_body_parts = image_result.get("visible_body_parts")
        observed_projection = image_result.get("observed_projection")
        projection_consistency = image_result.get("projection_consistency")
        quality_status = image_result.get("quality_status")
        quality_issue_codes = image_result.get("quality_issue_codes")
        if (
            not isinstance(is_valid_xray, bool)
            or species_consistency not in XRAY_IMAGE_QUALITY_SPECIES_CONSISTENCY
            or primary_body_part not in XRAY_IMAGE_QUALITY_BODY_PARTS
            or not isinstance(visible_body_parts, list)
            or not all(
                item in XRAY_IMAGE_QUALITY_BODY_PARTS for item in visible_body_parts
            )
            or len(visible_body_parts) != len(set(visible_body_parts))
            or observed_projection not in XRAY_IMAGE_QUALITY_PROJECTIONS
            or projection_consistency
            not in XRAY_IMAGE_QUALITY_PROJECTION_CONSISTENCY
            or quality_status not in XRAY_IMAGE_QUALITY_STATUSES
            or not isinstance(quality_issue_codes, list)
            or not all(
                item in XRAY_IMAGE_QUALITY_ISSUE_CODES
                for item in quality_issue_codes
            )
            or len(quality_issue_codes) != len(set(quality_issue_codes))
        ):
            raise XRayImageQualityContractError(
                f"xray_image_quality_image_{expected_sequence}_fields_invalid"
            )
        if (
            primary_body_part != "indeterminate"
            and primary_body_part not in visible_body_parts
        ):
            raise XRayImageQualityContractError(
                f"xray_image_quality_image_{expected_sequence}_body_part_invalid"
            )
        expected_consistency = _expected_projection_consistency(
            declared_projection=receipt.get("projection"),
            observed_projection=observed_projection,
        )
        if projection_consistency != expected_consistency:
            raise XRayImageQualityContractError(
                f"xray_image_quality_image_{expected_sequence}_projection_consistency_invalid"
            )
        if observed_projection in {"indeterminate", "lateral_indeterminate"} and (
            "projection_indeterminate" not in quality_issue_codes
        ):
            raise XRayImageQualityContractError(
                f"xray_image_quality_image_{expected_sequence}_projection_issue_missing"
            )
        if quality_status == "diagnostic":
            if quality_issue_codes:
                raise XRayImageQualityContractError(
                    f"xray_image_quality_image_{expected_sequence}_quality_invalid"
                )
        elif not quality_issue_codes:
            raise XRayImageQualityContractError(
                f"xray_image_quality_image_{expected_sequence}_quality_invalid"
            )

        if is_valid_xray:
            valid_count += 1
        elif (
            species_consistency != "indeterminate"
            or primary_body_part != "indeterminate"
            or visible_body_parts
            or observed_projection != "indeterminate"
            or projection_consistency != "indeterminate"
            or quality_status != "non_diagnostic"
            or "non_xray_or_unsupported" not in quality_issue_codes
        ):
            raise XRayImageQualityContractError(
                f"xray_image_quality_image_{expected_sequence}_invalid_xray_contract_invalid"
            )

    expected_status = (
        "complete"
        if valid_count == len(result_images)
        else "unavailable"
        if valid_count == 0
        else "partial"
    )
    if (
        result.get("result_status") not in XRAY_IMAGE_QUALITY_RESULT_STATUSES
        or result.get("result_status") != expected_status
    ):
        raise XRayImageQualityContractError(
            "xray_image_quality_result_status_invalid"
        )
    return dict(result)


__all__ = [
    "XRAY_IMAGE_QUALITY_BODY_PARTS",
    "XRAY_IMAGE_QUALITY_CONTRACT_V1",
    "XRAY_IMAGE_QUALITY_ISSUE_CODES",
    "XRAY_IMAGE_QUALITY_PROJECTIONS",
    "XRayImageQualityContractError",
    "validate_xray_image_quality_receipt_against_snapshot",
    "validate_xray_image_quality_result_contract",
]
