from __future__ import annotations

import hashlib
import asyncio
import json
import re
from typing import Protocol
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.crud.xray_accuracy.image_asset import XRayImageAssetDal

from .object_store import OSSObjectStore, ObjectStoreError, inspect_image_bytes


class SourceImageFetcher(Protocol):
    """Resolve an opaque ref through an approved credential service.

    Implementations must not treat the value as a caller-controlled URL; they
    own host/IP allowlists, redirect rejection, timeout and response-size
    limits before returning bytes.
    """

    async def fetch(self, *, tenant_id: str, source_image_ref: str) -> bytes: ...


class FailClosedSourceImageFetcher:
    async def fetch(self, *, tenant_id: str, source_image_ref: str) -> bytes:
        del tenant_id, source_image_ref
        raise ObjectStoreError("image_source_fetcher_not_configured")


class ApprovedManifestSourceImageFetcher:
    """Read approved non-production fixtures through an opaque ref manifest.

    This adapter is intentionally local-file based for isolated qualification
    only.  Callers submit opaque references; they never submit paths or URLs.
    Each manifest entry is bound to a relative path under ``root_dir`` and an
    expected SHA256.  A future credential service can implement the same
    ``SourceImageFetcher`` protocol without changing the ingest contract.
    """

    _REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,511}")
    _SHA256 = re.compile(r"[0-9a-f]{64}")
    _MAX_ENTRIES = 256
    _MAX_BYTES = 64 * 1024 * 1024

    def __init__(self, *, manifest_path: str | Path, root_dir: str | Path):
        self.manifest_path = Path(manifest_path).expanduser().resolve()
        self.root_dir = Path(root_dir).expanduser().resolve()
        if not self.manifest_path.is_file() or not self.root_dir.is_dir():
            raise ObjectStoreError("image_source_manifest_not_configured")
        try:
            loaded = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ObjectStoreError("image_source_manifest_invalid") from exc
        if not isinstance(loaded, dict) or len(loaded) > self._MAX_ENTRIES:
            raise ObjectStoreError("image_source_manifest_invalid")
        self._entries: dict[str, dict[str, str]] = {}
        for source_ref, item in loaded.items():
            if not isinstance(source_ref, str) or not self._REF.fullmatch(source_ref):
                raise ObjectStoreError("image_source_manifest_invalid")
            if not isinstance(item, dict):
                raise ObjectStoreError("image_source_manifest_invalid")
            relative_path = item.get("relative_path")
            sha256 = item.get("sha256")
            tenant_id = item.get("tenant_id")
            if (
                not isinstance(relative_path, str)
                or not relative_path.strip()
                or Path(relative_path).is_absolute()
                or not isinstance(sha256, str)
                or self._SHA256.fullmatch(sha256) is None
                or (tenant_id is not None and not isinstance(tenant_id, str))
            ):
                raise ObjectStoreError("image_source_manifest_invalid")
            self._entries[source_ref] = {
                "relative_path": relative_path,
                "sha256": sha256,
                **({"tenant_id": tenant_id} if tenant_id is not None else {}),
            }

    async def fetch(self, *, tenant_id: str, source_image_ref: str) -> bytes:
        entry = self._entries.get(source_image_ref)
        if entry is None:
            raise ObjectStoreError("image_source_forbidden")
        entry_tenant = entry.get("tenant_id")
        if entry_tenant is not None and entry_tenant != tenant_id:
            raise ObjectStoreError("image_source_forbidden")
        raw_candidate = self.root_dir / entry["relative_path"]
        if raw_candidate.is_symlink():
            raise ObjectStoreError("image_source_forbidden")
        candidate = raw_candidate.resolve()
        try:
            candidate.relative_to(self.root_dir)
        except ValueError as exc:
            raise ObjectStoreError("image_source_forbidden") from exc
        if not candidate.is_file():
            raise ObjectStoreError("image_source_unavailable")

        def _read() -> bytes:
            try:
                if candidate.stat().st_size > self._MAX_BYTES:
                    raise ObjectStoreError("image_content_too_large")
                content = candidate.read_bytes()
            except OSError as exc:
                raise ObjectStoreError("image_source_unavailable") from exc
            if not content or len(content) > self._MAX_BYTES:
                raise ObjectStoreError("image_content_too_large")
            if hashlib.sha256(content).hexdigest() != entry["sha256"]:
                raise ObjectStoreError("image_hash_mismatch")
            return content

        return await asyncio.to_thread(_read)

    def approved_refs(self, *, tenant_id: str) -> tuple[str, ...]:
        """Return only opaque refs approved for one qualification tenant."""
        refs = [
            source_ref
            for source_ref, entry in self._entries.items()
            if entry.get("tenant_id") in {None, tenant_id}
        ]
        if not refs:
            raise ObjectStoreError("image_source_forbidden")
        return tuple(refs)


class XRayImageIngestService:
    """Worker-only source fetch → validate → OSS upload flow."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None,
        object_store: OSSObjectStore,
        fetcher: SourceImageFetcher | None = None,
    ):
        self.session_factory = session_factory
        self.object_store = object_store
        self.fetcher = fetcher or FailClosedSourceImageFetcher()

    async def ingest_asset(self, *, tenant_id: str, asset_id: str) -> dict[str, str | int]:
        if self.session_factory is None:
            raise ObjectStoreError("image_ingest_session_factory_not_configured")
        async with self.session_factory() as db:
            return await self.ingest_asset_in_db(
                db, tenant_id=tenant_id, asset_id=asset_id
            )

    async def ingest_asset_in_db(
        self,
        db: AsyncSession,
        *,
        tenant_id: str,
        asset_id: str,
    ) -> dict[str, str | int]:
        """Ingest using a caller-owned transaction/session.

        The worker uses this form so the asset update and Study freeze can be
        committed atomically with the stage checkpoint.  It still keeps image
        bytes exclusively in worker memory and never places them in the DB.
        """
        dal = XRayImageAssetDal(db)
        asset = await dal.get_by_id(tenant_id=tenant_id, asset_id=asset_id)
        if asset is None:
            raise ObjectStoreError("image_asset_not_found")
        if asset.asset_status == "uploaded" and asset.content_sha256:
            return {
                "asset_id": asset.id,
                "content_sha256": asset.content_sha256,
                "asset_status": asset.asset_status,
            }
        content = await self.fetcher.fetch(
            tenant_id=tenant_id, source_image_ref=asset.source_image_ref
        )
        inspection = inspect_image_bytes(content, asset.mime_type)
        digest = hashlib.sha256(content).hexdigest()
        suffix = inspection.mime_type.split("/", 1)[1].replace("jpeg", "jpg")
        object_key = self.object_store.new_object_key(
            tenant_id=tenant_id,
            study_revision_id=asset.study_revision_id,
            source_index=asset.source_index,
            suffix=suffix,
            content_sha256=digest,
        )
        await self.object_store.put_bytes(
            object_key=object_key,
            content=content,
            mime_type=inspection.mime_type,
        )
        updated = await dal.mark_uploaded(
            tenant_id=tenant_id,
            asset_id=asset.id,
            object_key=object_key,
            content_sha256=digest,
            mime_type=inspection.mime_type,
            byte_size=inspection.byte_size,
            pixel_width=inspection.pixel_width,
            pixel_height=inspection.pixel_height,
            uploaded_at=datetime.utcnow(),
        )
        if updated is None:
            raise ObjectStoreError("image_asset_state_conflict")
        return {
            "asset_id": updated.id,
            "content_sha256": digest,
            "asset_status": updated.asset_status,
            "byte_size": inspection.byte_size,
        }


__all__ = [
    "ApprovedManifestSourceImageFetcher",
    "FailClosedSourceImageFetcher",
    "SourceImageFetcher",
    "XRayImageIngestService",
]
