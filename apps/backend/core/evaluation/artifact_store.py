"""Verified immutable JSON Artifact storage over the shared object gateway."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from apps.backend.core.imaging.object_store import (
    ObjectStorageGateway,
    ObjectStoreError,
    validate_object_key,
)


@dataclass(frozen=True)
class StoredJsonArtifact:
    object_ref: dict[str, Any]
    content_sha256: str
    content: bytes


class JsonArtifactStore:
    CONTENT_TYPE = "application/json"

    def __init__(self, gateway: ObjectStorageGateway):
        self.gateway = gateway

    async def store_json(self, *, object_key: str, payload: Any) -> StoredJsonArtifact:
        return await self.store_bytes(
            object_key=object_key,
            content=self.canonical_json_bytes(payload),
        )

    async def store_bytes(
        self, *, object_key: str, content: bytes
    ) -> StoredJsonArtifact:
        object_key = validate_object_key(object_key)
        if not content:
            raise ObjectStoreError("evaluation_artifact_content_empty")
        content_sha256 = hashlib.sha256(content).hexdigest()
        try:
            await self.gateway.head_object(object_key=object_key)
        except ObjectStoreError as exc:
            if str(exc) != "object_not_found":
                raise
            await self.gateway.put_bytes(
                object_key=object_key,
                content=content,
                mime_type=self.CONTENT_TYPE,
            )
        else:
            existing = await self.gateway.get_bytes(object_key=object_key)
            if existing != content:
                raise ObjectStoreError("evaluation_artifact_hash_drift")
        head = await self.gateway.head_object(object_key=object_key)
        if head.storage_profile != self.gateway.storage_profile:
            raise ObjectStoreError("evaluation_artifact_profile_drift")
        if (
            head.content_type
            and head.content_type.split(";", 1)[0].casefold() != self.CONTENT_TYPE
        ):
            raise ObjectStoreError("evaluation_artifact_content_type_drift")
        if head.size_bytes != len(content):
            raise ObjectStoreError("evaluation_artifact_size_drift")
        verified = await self.gateway.get_bytes(object_key=object_key)
        if (
            verified != content
            or hashlib.sha256(verified).hexdigest() != content_sha256
        ):
            raise ObjectStoreError("evaluation_artifact_hash_drift")
        return StoredJsonArtifact(
            object_ref={
                "storage_profile": head.storage_profile,
                "object_key": head.object_key,
                "object_version_id": head.object_version_id,
                "sha256": content_sha256,
                "size_bytes": head.size_bytes,
                "content_type": self.CONTENT_TYPE,
                "kms_key_version": head.kms_key_version,
            },
            content_sha256=content_sha256,
            content=content,
        )

    async def load_verified_json(
        self, *, object_ref: dict[str, Any], expected_sha256: str
    ) -> Any:
        required = {
            "storage_profile",
            "object_key",
            "sha256",
            "size_bytes",
            "content_type",
        }
        if not required.issubset(object_ref):
            raise ObjectStoreError("evaluation_artifact_ref_invalid")
        if self.gateway.storage_profile != object_ref["storage_profile"]:
            raise ObjectStoreError("object_storage_profile_mismatch")
        object_key = validate_object_key(str(object_ref["object_key"]))
        head = await self.gateway.head_object(object_key=object_key)
        if head.storage_profile != object_ref["storage_profile"]:
            raise ObjectStoreError("evaluation_artifact_profile_drift")
        expected_version = object_ref.get("object_version_id")
        if expected_version and head.object_version_id != expected_version:
            raise ObjectStoreError("evaluation_artifact_version_drift")
        if head.size_bytes != int(object_ref["size_bytes"]):
            raise ObjectStoreError("evaluation_artifact_size_drift")
        if str(object_ref["content_type"]).casefold() != self.CONTENT_TYPE:
            raise ObjectStoreError("evaluation_artifact_content_type_invalid")
        if (
            head.content_type
            and head.content_type.split(";", 1)[0].casefold() != self.CONTENT_TYPE
        ):
            raise ObjectStoreError("evaluation_artifact_content_type_invalid")
        content = await self.gateway.get_bytes(object_key=object_key)
        digest = hashlib.sha256(content).hexdigest()
        if (
            digest != expected_sha256
            or digest != object_ref["sha256"]
            or len(content) != int(object_ref["size_bytes"])
        ):
            raise ObjectStoreError("evaluation_artifact_hash_drift")
        try:
            return json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ObjectStoreError("evaluation_artifact_json_invalid") from exc

    @staticmethod
    def canonical_json_bytes(value: Any) -> bytes:
        try:
            return json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ObjectStoreError("evaluation_artifact_serialization_failed") from exc


__all__ = ["JsonArtifactStore", "StoredJsonArtifact"]
