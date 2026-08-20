"""Canonical manifests for current imaging facts.

The helpers are deliberately persistence-neutral.  Services provide ORM
objects, while the canonical payload contains only stable, non-sensitive
facts that can be reproduced from the database.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable


class ManifestContractError(ValueError):
    pass


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


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


def build_series_manifest(images: Iterable[Any]) -> CanonicalManifest:
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

    items: list[dict[str, Any]] = []
    for image in current.values():
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
    "build_series_manifest",
    "build_study_manifest",
    "canonical_json_bytes",
    "manifest_sha256",
]
