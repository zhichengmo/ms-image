"""Technical integrity checks for versioned XRay model results.

JSON Schema owns the result shape.  This module only checks references that
JSON Schema cannot prove against the images actually sent to the Provider.  It
must not infer, rewrite or otherwise judge medical content.
"""

from __future__ import annotations

from typing import Any, Mapping

from apps.backend.core.ai.gateway.contracts import AI_IMAGE_RECEIPT_V2

COMPLETE_MEDICAL_RESULT_V2 = "complete-medical-result.v2"
XRAY_RESULT_SCHEMA_V2 = "xray-complete-medical-result.v2"


class XRayResultContractError(ValueError):
    """Raised when a schema-valid XRay result has broken technical references."""


def validate_xray_result_contract(
    *,
    result: Mapping[str, Any],
    schema_contract_version: Any,
    image_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate v2 IDs and source facts against the actual egress receipt.

    Other schema versions are deliberately left untouched so historical v1
    Configs and Tasks keep their frozen behavior.
    """

    if schema_contract_version != COMPLETE_MEDICAL_RESULT_V2:
        return dict(result)
    if result.get("result_schema_version") != XRAY_RESULT_SCHEMA_V2:
        raise XRayResultContractError("provider_result_contract_version_invalid")

    receipt_images = image_receipt.get("images")
    if (
        image_receipt.get("contract_version") != AI_IMAGE_RECEIPT_V2
        or not isinstance(receipt_images, list)
        or image_receipt.get("image_count") != len(receipt_images)
    ):
        raise XRayResultContractError("provider_result_source_receipt_invalid")

    sent_by_image_id: dict[str, Mapping[str, Any]] = {}
    for item in receipt_images:
        if not isinstance(item, Mapping):
            raise XRayResultContractError("provider_result_source_receipt_invalid")
        image_id = item.get("image_id")
        if (
            not isinstance(image_id, str)
            or not image_id
            or image_id in sent_by_image_id
        ):
            raise XRayResultContractError("provider_result_source_receipt_invalid")
        sent_by_image_id[image_id] = item

    source_refs = result.get("source_refs")
    findings = result.get("findings")
    if not isinstance(source_refs, list) or not isinstance(findings, list):
        raise XRayResultContractError("provider_result_contract_invalid")

    source_ids: set[str] = set()
    for source_ref in source_refs:
        if not isinstance(source_ref, Mapping):
            raise XRayResultContractError("provider_result_contract_invalid")
        source_ref_id = source_ref.get("source_ref_id")
        if not isinstance(source_ref_id, str) or not source_ref_id:
            raise XRayResultContractError("provider_result_contract_invalid")
        if source_ref_id in source_ids:
            raise XRayResultContractError("provider_result_source_ref_id_duplicate")
        source_ids.add(source_ref_id)

        image_id = source_ref.get("image_id")
        sent = sent_by_image_id.get(image_id) if isinstance(image_id, str) else None
        if sent is None:
            raise XRayResultContractError("provider_result_source_image_not_sent")
        if source_ref.get("series_id") != sent.get("series_id"):
            raise XRayResultContractError(
                "provider_result_source_series_id_mismatch"
            )
        if source_ref.get("projection") != sent.get("projection"):
            raise XRayResultContractError(
                "provider_result_source_projection_mismatch"
            )
        if source_ref.get("manifest_sha256") != sent.get(
            "series_manifest_sha256"
        ):
            raise XRayResultContractError(
                "provider_result_source_manifest_sha256_mismatch"
            )

    finding_ids: set[str] = set()
    for finding in findings:
        if not isinstance(finding, Mapping):
            raise XRayResultContractError("provider_result_contract_invalid")
        finding_id = finding.get("finding_id")
        if not isinstance(finding_id, str) or not finding_id:
            raise XRayResultContractError("provider_result_contract_invalid")
        if finding_id in finding_ids:
            raise XRayResultContractError("provider_result_finding_id_duplicate")
        finding_ids.add(finding_id)
        referenced_source_ids = finding.get("source_ref_ids")
        if not isinstance(referenced_source_ids, list):
            raise XRayResultContractError("provider_result_contract_invalid")
        if any(source_id not in source_ids for source_id in referenced_source_ids):
            raise XRayResultContractError("provider_result_source_ref_missing")

    targeted_candidate = result.get("targeted_candidate")
    if targeted_candidate is not None:
        if not isinstance(targeted_candidate, Mapping):
            raise XRayResultContractError("provider_result_contract_invalid")
        source_finding_ids = targeted_candidate.get("source_finding_ids")
        if (
            not isinstance(source_finding_ids, list)
            or not source_finding_ids
            or not all(
                isinstance(finding_id, str) and finding_id
                for finding_id in source_finding_ids
            )
            or len(source_finding_ids) != len(set(source_finding_ids))
            or any(finding_id not in finding_ids for finding_id in source_finding_ids)
        ):
            raise XRayResultContractError(
                "provider_result_targeted_source_finding_missing"
            )

    return dict(result)


__all__ = [
    "COMPLETE_MEDICAL_RESULT_V2",
    "XRAY_RESULT_SCHEMA_V2",
    "XRayResultContractError",
    "validate_xray_result_contract",
]
