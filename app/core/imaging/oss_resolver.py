from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.ai.contracts import ProviderImageInput
from app.core.imaging.contracts import ImageResolverError
from app.crud.xray_accuracy.image_asset import XRayImageAssetDal

from .object_store import OSSObjectStore, ObjectStoreError, dicom_to_png, inspect_image_bytes


class XRayOSSImageResolver:
    """Resolve asset opaque IDs to worker-memory ProviderImageInput values."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        object_store: OSSObjectStore,
    ):
        self.session_factory = session_factory
        self.object_store = object_store

    async def resolve(
        self,
        *,
        tenant_id: str,
        run_id: str,
        manifest: list[dict[str, Any]],
    ) -> tuple[ProviderImageInput, ...]:
        del run_id
        if not manifest:
            raise ImageResolverError("image_manifest_invalid")
        try:
            indices = [int(item["source_index"]) for item in manifest]
            if indices != list(range(len(indices))):
                raise ImageResolverError("image_manifest_invalid")
            if len({str(item["source_image_ref"]) for item in manifest}) != len(manifest):
                raise ImageResolverError("image_manifest_invalid")
            async with self.session_factory() as db:
                dal = XRayImageAssetDal(db)
                resolved: list[ProviderImageInput] = []
                for item in manifest:
                    asset_id = str(item["source_image_ref"])
                    asset = await dal.get_by_id(tenant_id=tenant_id, asset_id=asset_id)
                    if (
                        asset is None
                        or asset.asset_status != "uploaded"
                        or not asset.object_key
                        or not asset.content_sha256
                    ):
                        raise ImageResolverError("image_source_unavailable")
                    if asset.source_index != int(item["source_index"]):
                        raise ImageResolverError("image_manifest_invalid")
                    expected_prefix = self.object_store.expected_object_prefix(
                        tenant_id=tenant_id,
                        study_revision_id=asset.study_revision_id,
                        source_index=asset.source_index,
                    )
                    if not asset.object_key.startswith(expected_prefix):
                        raise ImageResolverError("image_source_forbidden")
                    content = await self.object_store.get_bytes(object_key=asset.object_key)
                    digest = hashlib.sha256(content).hexdigest()
                    if digest != asset.content_sha256:
                        raise ImageResolverError("image_hash_mismatch")
                    inspection = inspect_image_bytes(content, asset.mime_type)
                    provider_content = content
                    provider_inspection = inspection
                    if inspection.mime_type == "application/dicom":
                        provider_content, provider_inspection = dicom_to_png(content)
                    sent_digest = hashlib.sha256(provider_content).hexdigest()
                    resolved.append(
                        ProviderImageInput(
                            source_index=asset.source_index,
                            source_image_ref=asset.id,
                            mime_type=provider_inspection.mime_type,
                            content=provider_content,
                            pixel_width=provider_inspection.pixel_width,
                            pixel_height=provider_inspection.pixel_height,
                            sent_sha256=sent_digest,
                        )
                    )
                return tuple(resolved)
        except ImageResolverError:
            raise
        except ObjectStoreError as exc:
            raise ImageResolverError("image_source_unavailable") from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise ImageResolverError("image_manifest_invalid") from exc


__all__ = ["XRayOSSImageResolver"]
