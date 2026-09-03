"""Technical integrity checks for normalized X-Ray anatomy localization."""

from __future__ import annotations

import json
from functools import lru_cache
from math import isfinite
from pathlib import Path
from typing import Any, Mapping

from apps.backend.core.ai.config_contract import TASK_REQUEST_SNAPSHOT_V3
from apps.backend.core.ai.gateway.contracts import AI_IMAGE_RECEIPT_V2
from apps.backend.core.ai.prompting.contracts import sha256_json
from apps.backend.core.imaging.manifest import (
    ManifestContractError,
    validate_frozen_study_series,
)

ANATOMY_LOCALIZATION_CONTRACT_V1 = "xray-anatomy-localization.v1"
ANATOMY_LABEL_CONTRACT_V1 = "xray-anatomy-labels.v1"
ANATOMY_LOCALIZATION_RESULT_STATUSES = frozenset(
    {"complete", "partial", "unavailable"}
)
ANATOMY_NOT_LOCALIZED_REASONS = frozenset(
    {"no_supported_anatomy_visible", "insufficient_localization_evidence"}
)


class AnatomyLocalizationContractError(ValueError):
    """Raised when a schema-valid localization result breaks frozen lineage."""


@lru_cache(maxsize=1)
def load_anatomy_label_contract() -> dict[str, tuple[str, ...]]:
    path = (
        Path(__file__).resolve().parents[4]
        / "prompts/xray/anatomy_labels.v1.json"
    )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AnatomyLocalizationContractError(
            "anatomy_label_contract_unavailable"
        ) from exc
    systems = payload.get("systems") if isinstance(payload, Mapping) else None
    if (
        payload.get("contract_version") != ANATOMY_LABEL_CONTRACT_V1
        or not isinstance(systems, list)
        or len(systems) != 6
    ):
        raise AnatomyLocalizationContractError("anatomy_label_contract_invalid")
    result: dict[str, tuple[str, ...]] = {}
    labels_seen: set[str] = set()
    for item in systems:
        if not isinstance(item, Mapping):
            raise AnatomyLocalizationContractError("anatomy_label_contract_invalid")
        system = item.get("system")
        labels = item.get("labels")
        if (
            not isinstance(system, str)
            or not system
            or system in result
            or not isinstance(labels, list)
            or not labels
            or not all(isinstance(label, str) and label for label in labels)
            or len(labels) != len(set(labels))
            or labels_seen.intersection(labels)
        ):
            raise AnatomyLocalizationContractError("anatomy_label_contract_invalid")
        result[system] = tuple(labels)
        labels_seen.update(labels)
    if len(labels_seen) != 38:
        raise AnatomyLocalizationContractError("anatomy_label_contract_invalid")
    return result


def anatomy_label_contract_sha256() -> str:
    labels = load_anatomy_label_contract()
    payload = {
        "contract_version": ANATOMY_LABEL_CONTRACT_V1,
        "systems": [
            {"system": system, "labels": list(system_labels)}
            for system, system_labels in labels.items()
        ],
    }
    return sha256_json(payload)


def validate_anatomy_localization_receipt_against_snapshot(
    *,
    snapshot: Mapping[str, Any],
    image_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Reproduce the v3 receipt lineage from immutable Task image facts."""

    if snapshot.get("snapshot_contract_version") != TASK_REQUEST_SNAPSHOT_V3:
        raise AnatomyLocalizationContractError(
            "anatomy_localization_snapshot_v3_required"
        )
    try:
        frozen_series = validate_frozen_study_series(
            snapshot.get("series"),
            resolved_manifest_sha256=snapshot.get("resolved_manifest_sha256"),
        )
    except ManifestContractError as exc:
        raise AnatomyLocalizationContractError(
            "anatomy_localization_snapshot_lineage_invalid"
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
    receipt_images = image_receipt.get("images")
    if (
        image_receipt.get("contract_version") != AI_IMAGE_RECEIPT_V2
        or not 2 <= len(expected_images) <= 5
        or image_receipt.get("image_count") != len(expected_images)
        or receipt_images != expected_images
    ):
        raise AnatomyLocalizationContractError(
            "anatomy_localization_snapshot_receipt_mismatch"
        )
    return dict(image_receipt)


def validate_anatomy_localization_result_contract(
    *,
    result: Mapping[str, Any],
    schema_contract_version: Any,
    image_receipt: Mapping[str, Any],
    expected_species: Any,
) -> dict[str, Any]:
    """Validate exact image coverage and bbox facts without medical inference."""

    if schema_contract_version != ANATOMY_LOCALIZATION_CONTRACT_V1:
        raise AnatomyLocalizationContractError(
            "provider_result_contract_version_unsupported"
        )
    if expected_species not in {"cat", "dog"}:
        raise AnatomyLocalizationContractError(
            "anatomy_localization_expected_species_invalid"
        )
    if (
        result.get("contract_version") != ANATOMY_LOCALIZATION_CONTRACT_V1
        or result.get("label_contract_version") != ANATOMY_LABEL_CONTRACT_V1
        or result.get("species") != expected_species
    ):
        raise AnatomyLocalizationContractError(
            "anatomy_localization_result_identity_invalid"
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
        raise AnatomyLocalizationContractError(
            "anatomy_localization_source_receipt_invalid"
        )

    labels_by_system = load_anatomy_label_contract()
    localized_count = 0
    for expected_sequence, (receipt, image_result) in enumerate(
        zip(receipt_images, result_images, strict=True), start=1
    ):
        if not isinstance(receipt, Mapping) or not isinstance(image_result, Mapping):
            raise AnatomyLocalizationContractError(
                "anatomy_localization_image_contract_invalid"
            )
        expected = {
            "image_id": receipt.get("image_id"),
            "series_id": receipt.get("series_id"),
            "sequence_no": receipt.get("sequence_no"),
            "projection": receipt.get("projection"),
            "series_manifest_sha256": receipt.get("series_manifest_sha256"),
        }
        if (
            expected["sequence_no"] != expected_sequence
            or any(not isinstance(expected[key], str) or not expected[key] for key in (
                "image_id",
                "series_id",
                "projection",
                "series_manifest_sha256",
            ))
        ):
            raise AnatomyLocalizationContractError(
                "anatomy_localization_source_receipt_invalid"
            )
        for field_name, expected_value in expected.items():
            if image_result.get(field_name) != expected_value:
                raise AnatomyLocalizationContractError(
                    "anatomy_localization_image_"
                    f"{expected_sequence}_{field_name}_mismatch"
                )

        status = image_result.get("status")
        reason_code = image_result.get("reason_code")
        organs = image_result.get("organs")
        if not isinstance(organs, list) or len(organs) > 38:
            raise AnatomyLocalizationContractError(
                "anatomy_localization_organs_invalid"
            )
        if status == "localized":
            if reason_code is not None or not organs:
                raise AnatomyLocalizationContractError(
                    "anatomy_localization_status_invalid"
                )
            localized_count += 1
        elif status == "not_localized":
            if organs or reason_code not in ANATOMY_NOT_LOCALIZED_REASONS:
                raise AnatomyLocalizationContractError(
                    "anatomy_localization_status_invalid"
                )
        else:
            raise AnatomyLocalizationContractError(
                "anatomy_localization_status_invalid"
            )

        labels_seen: set[str] = set()
        for organ in organs:
            if not isinstance(organ, Mapping):
                raise AnatomyLocalizationContractError(
                    "anatomy_localization_organ_invalid"
                )
            system = organ.get("system")
            label = organ.get("label")
            bbox = organ.get("bbox")
            if (
                not isinstance(system, str)
                or not isinstance(label, str)
                or label not in labels_by_system.get(system, ())
                or label in labels_seen
                or not isinstance(bbox, list)
                or len(bbox) != 4
                or not all(
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and isfinite(value)
                    and 0 <= value <= 1
                    for value in bbox
                )
                or bbox[0] >= bbox[2]
                or bbox[1] >= bbox[3]
            ):
                raise AnatomyLocalizationContractError(
                    "anatomy_localization_organ_invalid"
                )
            labels_seen.add(label)

    expected_status = (
        "complete"
        if localized_count == len(result_images)
        else "unavailable"
        if localized_count == 0
        else "partial"
    )
    if (
        result.get("result_status") not in ANATOMY_LOCALIZATION_RESULT_STATUSES
        or result.get("result_status") != expected_status
    ):
        raise AnatomyLocalizationContractError(
            "anatomy_localization_result_status_invalid"
        )
    return dict(result)


__all__ = [
    "ANATOMY_LABEL_CONTRACT_V1",
    "ANATOMY_LOCALIZATION_CONTRACT_V1",
    "AnatomyLocalizationContractError",
    "anatomy_label_contract_sha256",
    "load_anatomy_label_contract",
    "validate_anatomy_localization_receipt_against_snapshot",
    "validate_anatomy_localization_result_contract",
]
