"""Canonical manifests for current imaging facts.

The helpers are deliberately persistence-neutral.  Services provide ORM
objects, while the canonical payload contains only stable, non-sensitive
facts that can be reproduced from the database.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Iterable


class ManifestContractError(ValueError):
    pass


_SHA256 = re.compile(r"^[0-9a-f]{64}$")

PROJECTION_UNKNOWN = "UNKNOWN"
PROJECTION_PROVENANCE_KEY = "projection_provenance"
PROJECTION_SCHEMA_VERSION = "xray-projection.v1"
PROJECTION_SOURCE_CALLER = "caller_declared"
PROJECTION_SOURCE_LEGACY = "legacy_unspecified"
SERIES_IMAGE_MANIFEST_V2 = "series-image-manifest.v2"

_PROJECTION_SOURCES = frozenset(
    {PROJECTION_SOURCE_CALLER, PROJECTION_SOURCE_LEGACY}
)
_SERIES_IMAGE_ITEM_KEYS = frozenset(
    {
        "image_id",
        "series_id",
        "logical_image_key",
        "image_version_no",
        "sequence_no",
        "image_role",
        "image_kind",
        "file_format",
        "projection",
        "projection_provenance",
        "storage_profile",
        "object_key",
        "object_version_id",
        "sha256",
        "size_bytes",
        "content_type",
    }
)
_FROZEN_SERIES_KEYS = frozenset(
    {
        "series_id",
        "series_key",
        "series_no",
        "manifest_contract_version",
        "manifest_sha256",
        "actual_image_count",
        "ordered_images",
    }
)


@dataclass(frozen=True)
class CanonicalManifest:
    items: tuple[dict[str, Any], ...]
    sha256: str

    def as_list(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.items]


def canonical_json_bytes(value: Any) -> bytes:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ManifestContractError("manifest_value_not_canonical") from exc
    return encoded.encode("utf-8")


def manifest_sha256(items: Iterable[dict[str, Any]]) -> CanonicalManifest:
    frozen = tuple(dict(item) for item in items)
    digest = hashlib.sha256(canonical_json_bytes(list(frozen))).hexdigest()
    return CanonicalManifest(items=frozen, sha256=digest)


EMPTY_MANIFEST = manifest_sha256(())


def normalize_projection(value: Any) -> str:
    if not isinstance(value, str):
        raise ManifestContractError("image_projection_invalid")
    normalized = value.strip()
    if not normalized or len(normalized) > 64:
        raise ManifestContractError("image_projection_invalid")
    return normalized


def projection_provenance(*, source: str) -> dict[str, str]:
    if source not in _PROJECTION_SOURCES:
        raise ManifestContractError("image_projection_provenance_invalid")
    return {
        "source": source,
        "schema_version": PROJECTION_SCHEMA_VERSION,
    }


def projection_fact_from_image(image: Any) -> tuple[str, dict[str, str]]:
    """Return one honest projection fact without inferring medical content.

    New writes persist a caller-declared provenance object. Historical rows can
    lack both fields, so the compatibility path emits explicit ``UNKNOWN`` with
    ``legacy_unspecified`` provenance instead of guessing a projection.
    """

    raw_projection = getattr(image, "projection", None)
    metadata = getattr(image, "technical_metadata_json", None)
    raw_provenance = (
        metadata.get(PROJECTION_PROVENANCE_KEY)
        if isinstance(metadata, Mapping)
        else None
    )
    if raw_projection is None or not str(raw_projection).strip():
        if raw_provenance is not None:
            raise ManifestContractError("image_projection_provenance_orphaned")
        return (
            PROJECTION_UNKNOWN,
            projection_provenance(source=PROJECTION_SOURCE_LEGACY),
        )

    projection = normalize_projection(raw_projection)
    if raw_provenance is None:
        return (
            projection,
            projection_provenance(source=PROJECTION_SOURCE_LEGACY),
        )
    return projection, _normalize_projection_provenance(raw_provenance)


def build_projection_metadata(
    metadata: Mapping[str, Any] | None,
    *,
    source: str,
) -> dict[str, Any]:
    values = dict(metadata or {})
    if PROJECTION_PROVENANCE_KEY in values:
        raise ManifestContractError("image_projection_provenance_reserved")
    values[PROJECTION_PROVENANCE_KEY] = projection_provenance(source=source)
    return values


def _normalize_projection_provenance(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != {
        "source",
        "schema_version",
    }:
        raise ManifestContractError("image_projection_provenance_invalid")
    source = value.get("source")
    schema_version = value.get("schema_version")
    if (
        not isinstance(source, str)
        or source not in _PROJECTION_SOURCES
        or schema_version != PROJECTION_SCHEMA_VERSION
    ):
        raise ManifestContractError("image_projection_provenance_invalid")
    return projection_provenance(source=source)


def _ready_images_by_logical_key(images: Iterable[Any]) -> dict[str, Any]:
    current: dict[str, Any] = {}
    for image in images:
        if getattr(image, "status", None) != "ready":
            continue
        logical_key = str(getattr(image, "logical_image_key", "")).strip()
        if not logical_key:
            raise ManifestContractError("image_logical_key_missing")
        if logical_key in current:
            raise ManifestContractError("image_current_version_conflict")
        current[logical_key] = image
    return current


def build_series_manifest_legacy(images: Iterable[Any]) -> CanonicalManifest:
    """Reproduce the pre-D1 manifest exactly for frozen v1/v2 Task replay."""

    items: list[dict[str, Any]] = []
    for image in _ready_images_by_logical_key(images).values():
        required = {
            "id": getattr(image, "id", None),
            "sha256": getattr(image, "sha256", None),
            "size_bytes": getattr(image, "size_bytes", None),
            "content_type": getattr(image, "content_type", None),
            "object_key": getattr(image, "object_key", None),
            "storage_profile": getattr(image, "storage_profile", None),
        }
        if any(value is None or value == "" for value in required.values()):
            raise ManifestContractError("image_object_ref_incomplete")
        if not _SHA256.fullmatch(str(required["sha256"])):
            raise ManifestContractError("image_sha256_invalid")
        if int(required["size_bytes"]) < 1:
            raise ManifestContractError("image_size_invalid")
        items.append(
            {
                "image_id": str(required["id"]),
                "logical_image_key": str(image.logical_image_key),
                "image_version_no": int(image.image_version_no),
                "sequence_no": int(image.sequence_no),
                "image_role": str(image.image_role),
                "image_kind": str(image.image_kind),
                "file_format": str(image.file_format),
                "storage_profile": str(required["storage_profile"]),
                "object_key": str(required["object_key"]),
                "object_version_id": getattr(image, "object_version_id", None),
                "sha256": str(required["sha256"]),
                "size_bytes": int(required["size_bytes"]),
                "content_type": str(required["content_type"]),
            }
        )
    items.sort(
        key=lambda item: (
            item["sequence_no"],
            item["logical_image_key"],
            item["image_version_no"],
            item["image_id"],
        )
    )
    return manifest_sha256(items)


def build_series_manifest(images: Iterable[Any]) -> CanonicalManifest:
    """Build the D1 per-image manifest including projection provenance."""

    items: list[dict[str, Any]] = []
    for image in _ready_images_by_logical_key(images).values():
        required = {
            "id": getattr(image, "id", None),
            "series_id": getattr(image, "series_id", None),
            "sha256": getattr(image, "sha256", None),
            "size_bytes": getattr(image, "size_bytes", None),
            "content_type": getattr(image, "content_type", None),
            "object_key": getattr(image, "object_key", None),
            "storage_profile": getattr(image, "storage_profile", None),
        }
        if any(value is None or value == "" for value in required.values()):
            raise ManifestContractError("image_object_ref_incomplete")
        if not _SHA256.fullmatch(str(required["sha256"])):
            raise ManifestContractError("image_sha256_invalid")
        if int(required["size_bytes"]) < 1:
            raise ManifestContractError("image_size_invalid")
        projection, provenance = projection_fact_from_image(image)
        items.append(
            {
                "image_id": str(required["id"]),
                "series_id": str(required["series_id"]),
                "logical_image_key": str(image.logical_image_key),
                "image_version_no": int(image.image_version_no),
                "sequence_no": int(image.sequence_no),
                "image_role": str(image.image_role),
                "image_kind": str(image.image_kind),
                "file_format": str(image.file_format),
                "projection": projection,
                "projection_provenance": provenance,
                "storage_profile": str(required["storage_profile"]),
                "object_key": str(required["object_key"]),
                "object_version_id": getattr(image, "object_version_id", None),
                "sha256": str(required["sha256"]),
                "size_bytes": int(required["size_bytes"]),
                "content_type": str(required["content_type"]),
            }
        )
    items.sort(key=_series_image_sort_key)
    return manifest_sha256(items)


def validate_frozen_series_manifest(
    items: Any,
    *,
    series_id: str,
) -> CanonicalManifest:
    """Validate and hash immutable D1 items without reading current Image rows."""

    if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
        raise ManifestContractError("frozen_series_manifest_invalid")
    normalized: list[dict[str, Any]] = []
    logical_keys: set[str] = set()
    image_ids: set[str] = set()
    for value in items:
        if not isinstance(value, Mapping) or set(value) != _SERIES_IMAGE_ITEM_KEYS:
            raise ManifestContractError("frozen_series_manifest_invalid")
        item = dict(value)
        string_fields = (
            "image_id",
            "series_id",
            "logical_image_key",
            "image_role",
            "image_kind",
            "file_format",
            "storage_profile",
            "object_key",
            "content_type",
        )
        if any(
            not isinstance(item.get(field), str) or not item[field]
            for field in string_fields
        ):
            raise ManifestContractError("frozen_series_manifest_invalid")
        if item["series_id"] != series_id:
            raise ManifestContractError("frozen_series_manifest_series_mismatch")
        if (
            not isinstance(item.get("image_version_no"), int)
            or isinstance(item["image_version_no"], bool)
            or item["image_version_no"] < 1
            or not isinstance(item.get("sequence_no"), int)
            or isinstance(item["sequence_no"], bool)
            or item["sequence_no"] < 1
            or not isinstance(item.get("size_bytes"), int)
            or isinstance(item["size_bytes"], bool)
            or item["size_bytes"] < 1
            or not isinstance(item.get("sha256"), str)
            or _SHA256.fullmatch(item["sha256"]) is None
            or (
                item.get("object_version_id") is not None
                and not isinstance(item["object_version_id"], str)
            )
        ):
            raise ManifestContractError("frozen_series_manifest_invalid")
        projection = normalize_projection(item.get("projection"))
        if projection != item["projection"]:
            raise ManifestContractError("frozen_series_manifest_invalid")
        item["projection_provenance"] = _normalize_projection_provenance(
            item.get("projection_provenance")
        )
        if (
            item["logical_image_key"] in logical_keys
            or item["image_id"] in image_ids
        ):
            raise ManifestContractError("frozen_series_manifest_duplicate")
        logical_keys.add(item["logical_image_key"])
        image_ids.add(item["image_id"])
        normalized.append(item)
    if normalized != sorted(normalized, key=_series_image_sort_key):
        raise ManifestContractError("frozen_series_manifest_order_invalid")
    return manifest_sha256(normalized)


def validate_frozen_study_series(
    value: Any,
    *,
    resolved_manifest_sha256: Any,
) -> tuple[dict[str, Any], ...]:
    """Validate the complete D1 Study snapshot and its canonical order/hash."""

    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes, bytearray))
        or not isinstance(resolved_manifest_sha256, str)
        or _SHA256.fullmatch(resolved_manifest_sha256) is None
    ):
        raise ManifestContractError("frozen_study_manifest_invalid")
    normalized_series: list[dict[str, Any]] = []
    study_items: list[dict[str, Any]] = []
    image_ids: set[str] = set()
    for series_value in value:
        if (
            not isinstance(series_value, Mapping)
            or set(series_value) != _FROZEN_SERIES_KEYS
        ):
            raise ManifestContractError("frozen_study_manifest_invalid")
        series_id = series_value.get("series_id")
        series_key = series_value.get("series_key")
        series_no = series_value.get("series_no")
        manifest_sha = series_value.get("manifest_sha256")
        image_count = series_value.get("actual_image_count")
        if (
            not isinstance(series_id, str)
            or not series_id
            or not isinstance(series_key, str)
            or not series_key
            or (
                series_no is not None
                and (
                    not isinstance(series_no, int)
                    or isinstance(series_no, bool)
                )
            )
            or series_value.get("manifest_contract_version")
            != SERIES_IMAGE_MANIFEST_V2
            or not isinstance(manifest_sha, str)
            or _SHA256.fullmatch(manifest_sha) is None
            or not isinstance(image_count, int)
            or isinstance(image_count, bool)
            or image_count < 0
        ):
            raise ManifestContractError("frozen_study_manifest_invalid")
        image_manifest = validate_frozen_series_manifest(
            series_value.get("ordered_images"),
            series_id=series_id,
        )
        if (
            image_manifest.sha256 != manifest_sha
            or len(image_manifest.items) != image_count
        ):
            raise ManifestContractError("frozen_series_manifest_mismatch")
        for item in image_manifest.items:
            if item["image_id"] in image_ids:
                raise ManifestContractError("frozen_study_image_duplicate")
            image_ids.add(item["image_id"])
        normalized_series.append(
            {
                "series_id": series_id,
                "series_key": series_key,
                "series_no": series_no,
                "manifest_contract_version": SERIES_IMAGE_MANIFEST_V2,
                "manifest_sha256": manifest_sha,
                "actual_image_count": image_count,
                "ordered_images": image_manifest.as_list(),
            }
        )
        study_items.append(
            {
                "series_id": series_id,
                "series_key": series_key,
                "series_no": series_no,
                "actual_image_count": image_count,
                "manifest_sha256": manifest_sha,
            }
        )
    ordered = sorted(
        normalized_series,
        key=lambda item: (
            item["series_no"] is None,
            item["series_no"] if item["series_no"] is not None else 0,
            item["series_key"],
            item["series_id"],
        ),
    )
    if normalized_series != ordered:
        raise ManifestContractError("frozen_study_manifest_order_invalid")
    if manifest_sha256(study_items).sha256 != resolved_manifest_sha256:
        raise ManifestContractError("frozen_study_manifest_mismatch")
    return tuple(normalized_series)


def _series_image_sort_key(item: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        item["sequence_no"],
        item["logical_image_key"],
        item["image_version_no"],
        item["image_id"],
    )


def build_study_manifest(series_rows: Iterable[Any]) -> CanonicalManifest:
    items: list[dict[str, Any]] = []
    for series in series_rows:
        actual_count = int(getattr(series, "actual_image_count", 0))
        manifest = getattr(series, "manifest_sha256", None)
        if manifest is None and actual_count == 0:
            manifest = EMPTY_MANIFEST.sha256
        if not isinstance(manifest, str) or not _SHA256.fullmatch(manifest):
            raise ManifestContractError("series_manifest_incomplete")
        items.append(
            {
                "series_id": str(series.id),
                "series_key": str(series.series_key),
                "series_no": series.series_no,
                "actual_image_count": actual_count,
                "manifest_sha256": manifest,
            }
        )
    items.sort(
        key=lambda item: (
            item["series_no"] is None,
            item["series_no"] if item["series_no"] is not None else 0,
            item["series_key"],
            item["series_id"],
        )
    )
    return manifest_sha256(items)


__all__ = [
    "CanonicalManifest",
    "EMPTY_MANIFEST",
    "ManifestContractError",
    "PROJECTION_PROVENANCE_KEY",
    "PROJECTION_SCHEMA_VERSION",
    "PROJECTION_SOURCE_CALLER",
    "PROJECTION_SOURCE_LEGACY",
    "PROJECTION_UNKNOWN",
    "SERIES_IMAGE_MANIFEST_V2",
    "build_projection_metadata",
    "build_series_manifest",
    "build_series_manifest_legacy",
    "build_study_manifest",
    "canonical_json_bytes",
    "manifest_sha256",
    "normalize_projection",
    "projection_fact_from_image",
    "projection_provenance",
    "validate_frozen_series_manifest",
    "validate_frozen_study_series",
]
