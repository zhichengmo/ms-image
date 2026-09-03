"""Technical integrity checks for X-Ray StudyScreening results."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from apps.backend.core.ai.gateway.contracts import AI_IMAGE_RECEIPT_V2

XRAY_STUDY_SCREENING_CONTRACT_V1 = "xray-study-screening.v1"
XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2 = (
    "xray-study-screening-provider.v2"
)
XRAY_STUDY_SCREENING_CANONICAL_CONTRACT_V2 = "xray-study-screening.v2"


class XRayStudyScreeningContractError(ValueError):
    """Raised when schema-valid screening output breaks frozen lineage."""


def validate_xray_study_screening_result_contract(
    *,
    result: Mapping[str, Any],
    schema_contract_version: Any,
    image_receipt: Mapping[str, Any],
    expected_species: Any,
) -> dict[str, Any]:
    """Validate identity, source references and cross-reference integrity only."""

    if schema_contract_version != XRAY_STUDY_SCREENING_CONTRACT_V1:
        raise XRayStudyScreeningContractError(
            "provider_result_contract_version_unsupported"
        )
    if result.get("contract_version") != XRAY_STUDY_SCREENING_CONTRACT_V1:
        raise XRayStudyScreeningContractError(
            "study_screening_contract_version_invalid"
        )
    if expected_species not in {"cat", "dog"}:
        raise XRayStudyScreeningContractError(
            "study_screening_expected_species_invalid"
        )
    if result.get("species") != expected_species:
        raise XRayStudyScreeningContractError("study_screening_species_mismatch")

    receipt_images = image_receipt.get("images")
    if (
        image_receipt.get("contract_version") != AI_IMAGE_RECEIPT_V2
        or not isinstance(receipt_images, list)
        or not 2 <= len(receipt_images) <= 5
        or image_receipt.get("image_count") != len(receipt_images)
    ):
        raise XRayStudyScreeningContractError(
            "study_screening_source_receipt_invalid"
        )

    receipt_by_image_id: dict[str, Mapping[str, Any]] = {}
    receipt_by_sequence: dict[int, Mapping[str, Any]] = {}
    for item in receipt_images:
        if not isinstance(item, Mapping):
            raise XRayStudyScreeningContractError(
                "study_screening_source_receipt_invalid"
            )
        image_id = item.get("image_id")
        sequence_no = item.get("sequence_no")
        if (
            not isinstance(image_id, str)
            or not image_id
            or image_id in receipt_by_image_id
            or not isinstance(sequence_no, int)
            or isinstance(sequence_no, bool)
            or sequence_no in receipt_by_sequence
        ):
            raise XRayStudyScreeningContractError(
                "study_screening_source_receipt_invalid"
            )
        receipt_by_image_id[image_id] = item
        receipt_by_sequence[sequence_no] = item

    source_refs = result.get("source_refs")
    if not isinstance(source_refs, list):
        raise XRayStudyScreeningContractError("study_screening_result_invalid")
    source_ids: set[str] = set()
    referenced_images: set[str] = set()
    for source_ref in source_refs:
        if not isinstance(source_ref, Mapping):
            raise XRayStudyScreeningContractError("study_screening_result_invalid")
        source_ref_id = source_ref.get("source_ref_id")
        image_id = source_ref.get("image_id")
        sequence_no = source_ref.get("sequence_no")
        if (
            not isinstance(source_ref_id, str)
            or not source_ref_id
            or source_ref_id in source_ids
            or not isinstance(image_id, str)
            or not image_id
        ):
            raise XRayStudyScreeningContractError(
                "study_screening_source_ref_invalid"
            )
        sent = receipt_by_image_id.get(image_id)
        if sent is None or receipt_by_sequence.get(sequence_no) is not sent:
            raise XRayStudyScreeningContractError(
                "study_screening_source_image_not_sent"
            )
        if source_ref.get("series_id") != sent.get("series_id"):
            raise XRayStudyScreeningContractError(
                "study_screening_source_series_id_mismatch"
            )
        if source_ref.get("series_manifest_sha256") != sent.get(
            "series_manifest_sha256"
        ):
            raise XRayStudyScreeningContractError(
                "study_screening_source_manifest_sha256_mismatch"
            )
        if source_ref.get("projection") != sent.get("projection"):
            raise XRayStudyScreeningContractError(
                "study_screening_source_projection_mismatch"
            )
        source_ids.add(source_ref_id)
        referenced_images.add(image_id)

    if referenced_images != set(receipt_by_image_id):
        raise XRayStudyScreeningContractError(
            "study_screening_source_coverage_mismatch"
        )

    for collection_name, id_key in (
        ("technical_limitations", "limitation_id"),
        ("emergency_signals", "signal_id"),
        ("screening_findings", "finding_id"),
    ):
        collection = result.get(collection_name)
        if not isinstance(collection, list):
            raise XRayStudyScreeningContractError("study_screening_result_invalid")
        item_ids: set[str] = set()
        for item in collection:
            if not isinstance(item, Mapping):
                raise XRayStudyScreeningContractError(
                    "study_screening_result_invalid"
                )
            item_id = item.get(id_key)
            referenced_source_ids = item.get("source_ref_ids")
            if (
                not isinstance(item_id, str)
                or not item_id
                or item_id in item_ids
                or not isinstance(referenced_source_ids, list)
                or not referenced_source_ids
                or len(referenced_source_ids) != len(set(referenced_source_ids))
                or any(source_id not in source_ids for source_id in referenced_source_ids)
            ):
                raise XRayStudyScreeningContractError(
                    "study_screening_cross_reference_invalid"
                )
            item_ids.add(item_id)

    requiring = result.get("families_requiring_analysis")
    not_assessed = result.get("families_not_assessed")
    coverage = result.get("coverage_summary")
    assessed = coverage.get("assessed_families") if isinstance(coverage, Mapping) else None
    if (
        not isinstance(requiring, list)
        or not isinstance(not_assessed, list)
        or not isinstance(assessed, list)
        or set(requiring) & set(not_assessed)
        or set(assessed) & set(not_assessed)
    ):
        raise XRayStudyScreeningContractError(
            "study_screening_family_coverage_invalid"
        )

    return dict(result)


def _validated_provider_v2_receipt_images(
    image_receipt: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(image_receipt, Mapping):
        raise XRayStudyScreeningContractError(
            "study_screening_source_receipt_invalid"
        )
    receipt_images = image_receipt.get("images")
    if (
        image_receipt.get("contract_version") != AI_IMAGE_RECEIPT_V2
        or not isinstance(receipt_images, list)
        or not 2 <= len(receipt_images) <= 5
        or image_receipt.get("image_count") != len(receipt_images)
    ):
        raise XRayStudyScreeningContractError(
            "study_screening_source_receipt_invalid"
        )

    seen_image_ids: set[str] = set()
    seen_sequences: set[int] = set()
    validated: list[Mapping[str, Any]] = []
    for item in receipt_images:
        if not isinstance(item, Mapping):
            raise XRayStudyScreeningContractError(
                "study_screening_source_receipt_invalid"
            )
        image_id = item.get("image_id")
        sequence_no = item.get("sequence_no")
        series_id = item.get("series_id")
        manifest_sha256 = item.get("series_manifest_sha256")
        projection = item.get("projection")
        projection_provenance = item.get("projection_provenance")
        if (
            not isinstance(image_id, str)
            or not image_id
            or image_id in seen_image_ids
            or not isinstance(sequence_no, int)
            or isinstance(sequence_no, bool)
            or not 1 <= sequence_no <= 5
            or sequence_no in seen_sequences
            or not isinstance(series_id, str)
            or not series_id
            or not isinstance(manifest_sha256, str)
            or len(manifest_sha256) != 64
            or any(char not in "0123456789abcdef" for char in manifest_sha256)
            or (projection is not None and not isinstance(projection, str))
            or not isinstance(projection_provenance, Mapping)
        ):
            raise XRayStudyScreeningContractError(
                "study_screening_source_receipt_invalid"
            )
        seen_image_ids.add(image_id)
        seen_sequences.add(sequence_no)
        validated.append(item)
    return tuple(sorted(validated, key=lambda item: item["sequence_no"]))


def _validate_provider_v2_medical_references(
    *,
    result: Mapping[str, Any],
    source_ids: set[str],
) -> None:
    for collection_name, id_key in (
        ("technical_limitations", "limitation_id"),
        ("emergency_signals", "signal_id"),
        ("screening_findings", "finding_id"),
    ):
        collection = result.get(collection_name)
        if not isinstance(collection, list):
            raise XRayStudyScreeningContractError(
                "study_screening_result_invalid"
            )
        item_ids: set[str] = set()
        for item in collection:
            if not isinstance(item, Mapping):
                raise XRayStudyScreeningContractError(
                    "study_screening_result_invalid"
                )
            item_id = item.get(id_key)
            referenced_source_ids = item.get("source_ref_ids")
            if (
                not isinstance(item_id, str)
                or not item_id
                or item_id in item_ids
                or not isinstance(referenced_source_ids, list)
                or not referenced_source_ids
                or len(referenced_source_ids) != len(set(referenced_source_ids))
                or any(
                    source_id not in source_ids
                    for source_id in referenced_source_ids
                )
            ):
                raise XRayStudyScreeningContractError(
                    "study_screening_cross_reference_invalid"
                )
            item_ids.add(item_id)

    requiring = result.get("families_requiring_analysis")
    not_assessed = result.get("families_not_assessed")
    coverage = result.get("coverage_summary")
    assessed = (
        coverage.get("assessed_families")
        if isinstance(coverage, Mapping)
        else None
    )
    if (
        not isinstance(requiring, list)
        or not isinstance(not_assessed, list)
        or not isinstance(assessed, list)
        or set(requiring) & set(not_assessed)
        or set(assessed) & set(not_assessed)
    ):
        raise XRayStudyScreeningContractError(
            "study_screening_family_coverage_invalid"
        )


def validate_xray_study_screening_provider_result_contract(
    *,
    result: Mapping[str, Any],
    schema_contract_version: Any,
    image_receipt: Mapping[str, Any],
    expected_species: Any,
) -> dict[str, Any]:
    """Validate the v2 Provider payload without adding receipt-owned facts."""

    if schema_contract_version != XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2:
        raise XRayStudyScreeningContractError(
            "provider_result_contract_version_unsupported"
        )
    if result.get("contract_version") != XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2:
        raise XRayStudyScreeningContractError(
            "study_screening_contract_version_invalid"
        )
    if expected_species not in {"cat", "dog"}:
        raise XRayStudyScreeningContractError(
            "study_screening_expected_species_invalid"
        )
    if result.get("species") != expected_species:
        raise XRayStudyScreeningContractError(
            "study_screening_species_mismatch"
        )

    receipt_images = _validated_provider_v2_receipt_images(image_receipt)
    receipt_by_image_id = {item["image_id"]: item for item in receipt_images}
    source_refs = result.get("source_refs")
    if not isinstance(source_refs, list):
        raise XRayStudyScreeningContractError("study_screening_result_invalid")

    source_ids: set[str] = set()
    referenced_images: set[str] = set()
    for source_ref in source_refs:
        if (
            not isinstance(source_ref, Mapping)
            or set(source_ref) != {"source_ref_id", "image_id"}
        ):
            raise XRayStudyScreeningContractError(
                "study_screening_source_ref_invalid"
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
            raise XRayStudyScreeningContractError(
                "study_screening_source_ref_invalid"
            )
        if image_id not in receipt_by_image_id:
            raise XRayStudyScreeningContractError(
                "study_screening_source_image_not_sent"
            )
        source_ids.add(source_ref_id)
        referenced_images.add(image_id)

    if referenced_images != set(receipt_by_image_id):
        raise XRayStudyScreeningContractError(
            "study_screening_source_coverage_mismatch"
        )

    _validate_provider_v2_medical_references(
        result=result,
        source_ids=source_ids,
    )
    return dict(result)


def canonicalize_xray_study_screening_result(
    *,
    provider_result: Mapping[str, Any],
    schema_contract_version: Any,
    image_receipt: Mapping[str, Any],
    expected_species: Any,
) -> dict[str, Any]:
    """Add only receipt-owned lineage to a validated v2 Provider result."""

    validated_provider = validate_xray_study_screening_provider_result_contract(
        result=provider_result,
        schema_contract_version=schema_contract_version,
        image_receipt=image_receipt,
        expected_species=expected_species,
    )
    receipt_images = _validated_provider_v2_receipt_images(image_receipt)
    source_ref_by_image_id = {
        item["image_id"]: item["source_ref_id"]
        for item in validated_provider["source_refs"]
    }

    canonical = deepcopy(validated_provider)
    canonical["contract_version"] = XRAY_STUDY_SCREENING_CANONICAL_CONTRACT_V2
    canonical["source_refs"] = [
        {
            "source_ref_id": source_ref_by_image_id[item["image_id"]],
            "image_id": item["image_id"],
            "sequence_no": item["sequence_no"],
            "series_id": item["series_id"],
            "series_manifest_sha256": item["series_manifest_sha256"],
            "projection": item.get("projection"),
            "projection_provenance": deepcopy(item["projection_provenance"]),
        }
        for item in receipt_images
    ]
    return canonical


__all__ = [
    "XRAY_STUDY_SCREENING_CANONICAL_CONTRACT_V2",
    "XRAY_STUDY_SCREENING_CONTRACT_V1",
    "XRAY_STUDY_SCREENING_PROVIDER_CONTRACT_V2",
    "XRayStudyScreeningContractError",
    "canonicalize_xray_study_screening_result",
    "validate_xray_study_screening_provider_result_contract",
    "validate_xray_study_screening_result_contract",
]
