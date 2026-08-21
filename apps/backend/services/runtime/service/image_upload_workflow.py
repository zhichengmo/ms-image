"""Transactional upload orchestration owned by :class:`ImageService`.

The API layer supplies the authenticated requester and the configured object-store
factory.  This module keeps the required DB -> object storage -> DB sequencing,
identity checks, and multipart-session compensation inside the existing Image
service boundary; it does not introduce another persistence or domain service.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Awaitable, Callable

from apps.backend.core.config import settings
from apps.backend.core.imaging.object_store import (
    ObjectStorageGateway,
    ObjectStoreError,
    UploadGrant,
)
from apps.backend.schemas.image import (
    ImageAbortCommand,
    ImageCompleteUploadRequest,
    ImageListMultipartPartsRequest,
    ImageMultipartPartReceipt,
    ImageMultipartPartsResponse,
    ImageMultipartUploadTicket,
    ImagePrepareMultipartRequest,
    ImagePreparePartsRequest,
    ImagePrepareUploadRequest,
    ImageReplaceMultipartRequest,
    ImageReplaceRequest,
    ImageResponse,
    ImageSignedPart,
    ImageUploadTicket,
)

if TYPE_CHECKING:
    from apps.backend.services.runtime.service.image_service import ImageService


GatewayFactory = Callable[[], ObjectStorageGateway]
MultipartPreparePayload = ImagePrepareMultipartRequest | ImageReplaceMultipartRequest
MultipartPrepareMethod = Callable[..., Awaitable[ImageResponse]]


class ImageUploadWorkflow:
    """Coordinates upload workflows while ImageService remains the domain owner."""

    def __init__(self, service: ImageService):
        self._service = service

    @staticmethod
    def _upload_expiry() -> tuple[int, datetime]:
        ttl_seconds = int(settings.OSS_SIGNED_URL_TTL_SECONDS)
        if ttl_seconds < 1:
            raise ObjectStoreError("object_signed_url_ttl_invalid")
        return ttl_seconds, datetime.utcnow() + timedelta(seconds=ttl_seconds)

    @staticmethod
    def _assert_grant_identity(
        *,
        grant: UploadGrant,
        image: ImageResponse,
        upload_mode: str,
        require_session: bool = False,
    ) -> None:
        if require_session and not grant.upload_session_ref:
            raise ObjectStoreError("multipart_upload_session_missing")
        if (
            grant.storage_profile != image.storage_profile
            or grant.object_key != image.object_key
            or grant.upload_mode != upload_mode
        ):
            raise ObjectStoreError("object_upload_grant_identity_conflict")

    @staticmethod
    def _assert_storage_profile(
        *, gateway: ObjectStorageGateway, storage_profile: str
    ) -> None:
        if gateway.storage_profile != storage_profile:
            raise ObjectStoreError("object_storage_profile_mismatch")

    async def issue_direct_upload(
        self,
        *,
        payload: ImagePrepareUploadRequest,
        requester_id: str,
        gateway_factory: GatewayFactory,
    ) -> ImageUploadTicket:
        gateway = gateway_factory()
        ttl_seconds, expires_at = self._upload_expiry()
        async with self._service.db.begin():
            image = await self._service.prepare_direct_upload(
                payload=payload,
                requester_id=requester_id,
                storage_profile=gateway.storage_profile,
                upload_expires_at=expires_at,
            )
        grant = await gateway.prepare_direct_upload(
            object_key=image.object_key,
            content_type=payload.declared_content_type,
            expires_seconds=ttl_seconds,
        )
        self._assert_grant_identity(
            grant=grant, image=image, upload_mode="direct_put"
        )
        return ImageUploadTicket(
            image=image,
            generation=image.image_version_no,
            upload_mode=grant.upload_mode,
            required_headers=grant.required_headers,
            expires_at=expires_at,
            signed_url=grant.signed_url,
        )

    async def issue_direct_replacement(
        self,
        *,
        payload: ImageReplaceRequest,
        requester_id: str,
        gateway_factory: GatewayFactory,
    ) -> ImageUploadTicket:
        gateway = gateway_factory()
        ttl_seconds, expires_at = self._upload_expiry()
        async with self._service.db.begin():
            image = await self._service.prepare_direct_replacement(
                payload=payload,
                requester_id=requester_id,
                storage_profile=gateway.storage_profile,
                upload_expires_at=expires_at,
            )
        grant = await gateway.prepare_direct_upload(
            object_key=image.object_key,
            content_type=payload.declared_content_type,
            expires_seconds=ttl_seconds,
        )
        self._assert_grant_identity(
            grant=grant, image=image, upload_mode="direct_put"
        )
        return ImageUploadTicket(
            image=image,
            generation=image.image_version_no,
            upload_mode=grant.upload_mode,
            required_headers=grant.required_headers,
            expires_at=expires_at,
            signed_url=grant.signed_url,
        )

    async def issue_multipart_upload(
        self,
        *,
        payload: ImagePrepareMultipartRequest,
        requester_id: str,
        gateway_factory: GatewayFactory,
    ) -> ImageMultipartUploadTicket:
        return await self._issue_multipart_upload(
            payload=payload,
            requester_id=requester_id,
            gateway_factory=gateway_factory,
            prepare_method=self._service.prepare_multipart_upload,
        )

    async def issue_multipart_replacement(
        self,
        *,
        payload: ImageReplaceMultipartRequest,
        requester_id: str,
        gateway_factory: GatewayFactory,
    ) -> ImageMultipartUploadTicket:
        return await self._issue_multipart_upload(
            payload=payload,
            requester_id=requester_id,
            gateway_factory=gateway_factory,
            prepare_method=self._service.prepare_multipart_replacement,
        )

    async def _issue_multipart_upload(
        self,
        *,
        payload: MultipartPreparePayload,
        requester_id: str,
        gateway_factory: GatewayFactory,
        prepare_method: MultipartPrepareMethod,
    ) -> ImageMultipartUploadTicket:
        gateway = gateway_factory()
        ttl_seconds, expires_at = self._upload_expiry()
        grant: UploadGrant | None = None
        created_session = False
        try:
            async with self._service.db.begin():
                image = await prepare_method(
                    payload=payload,
                    requester_id=requester_id,
                    storage_profile=gateway.storage_profile,
                    upload_expires_at=expires_at,
                )
                candidate = await self._service.get_upload_operation_candidate(
                    image_id=image.id,
                    requester_id=requester_id,
                    expected_state_version=image.state_version,
                    generation=image.image_version_no,
                    operation="multipart_prepare",
                )
            if candidate.upload_session_ref:
                upload_session_ref = candidate.upload_session_ref
                required_headers = {"Content-Type": payload.declared_content_type}
            else:
                grant = await gateway.initiate_multipart_upload(
                    object_key=image.object_key,
                    content_type=payload.declared_content_type,
                    expires_seconds=ttl_seconds,
                )
                created_session = bool(grant.upload_session_ref)
                self._assert_grant_identity(
                    grant=grant,
                    image=image,
                    upload_mode="multipart",
                    require_session=True,
                )
                upload_session_ref = str(grant.upload_session_ref)
                required_headers = grant.required_headers
                async with self._service.db.begin():
                    image = await self._service.bind_multipart_upload_session(
                        image_id=image.id,
                        requester_id=requester_id,
                        expected_state_version=image.state_version,
                        generation=image.image_version_no,
                        upload_session_ref=upload_session_ref,
                        upload_expires_at=expires_at,
                    )
            return ImageMultipartUploadTicket(
                image=image,
                generation=image.image_version_no,
                upload_mode="multipart",
                required_headers=required_headers,
                expires_at=expires_at,
                upload_session_ref=upload_session_ref,
            )
        except Exception:
            if created_session and grant is not None:
                try:
                    await gateway.abort_multipart_upload(
                        object_key=grant.object_key,
                        upload_session_ref=str(grant.upload_session_ref),
                    )
                except Exception:
                    pass
            raise

    async def issue_multipart_part_urls(
        self,
        *,
        payload: ImagePreparePartsRequest,
        requester_id: str,
        gateway_factory: GatewayFactory,
    ) -> ImageMultipartPartsResponse:
        gateway = gateway_factory()
        async with self._service.db.begin():
            candidate = await self._service.get_upload_operation_candidate(
                image_id=payload.id,
                requester_id=requester_id,
                expected_state_version=payload.expected_state_version,
                generation=payload.generation,
                operation="parts",
            )
            part_numbers = self._service.validate_multipart_part_numbers(
                candidate, payload.part_numbers
            )
        self._assert_storage_profile(
            gateway=gateway, storage_profile=candidate.storage_profile
        )
        signed = await gateway.sign_multipart_parts(
            object_key=candidate.object_key,
            upload_session_ref=str(candidate.upload_session_ref),
            part_numbers=part_numbers,
        )
        return ImageMultipartPartsResponse(
            id=candidate.image_id,
            generation=candidate.generation,
            parts=[
                ImageSignedPart(part_number=number, signed_url=signed[number])
                for number in part_numbers
            ],
        )

    async def list_multipart_parts(
        self,
        *,
        payload: ImageListMultipartPartsRequest,
        requester_id: str,
        gateway_factory: GatewayFactory,
    ) -> list[ImageMultipartPartReceipt]:
        gateway = gateway_factory()
        async with self._service.db.begin():
            candidate = await self._service.get_upload_operation_candidate(
                image_id=payload.id,
                requester_id=requester_id,
                expected_state_version=payload.expected_state_version,
                generation=payload.generation,
                operation="list_parts",
            )
        self._assert_storage_profile(
            gateway=gateway, storage_profile=candidate.storage_profile
        )
        parts = await gateway.list_multipart_parts(
            object_key=candidate.object_key,
            upload_session_ref=str(candidate.upload_session_ref),
        )
        return [
            ImageMultipartPartReceipt(
                part_number=item.part_number,
                etag=item.etag,
                size_bytes=item.size_bytes,
            )
            for item in parts
        ]

    async def complete_upload(
        self,
        *,
        payload: ImageCompleteUploadRequest,
        requester_id: str,
        gateway_factory: GatewayFactory,
    ) -> ImageResponse:
        gateway = gateway_factory()
        async with self._service.db.begin():
            candidate = await self._service.get_upload_operation_candidate(
                image_id=payload.id,
                requester_id=requester_id,
                expected_state_version=payload.expected_state_version,
                generation=payload.generation,
                operation="complete",
            )
            parts = self._service.build_multipart_completion_parts(
                candidate, payload.parts
            )
            multipart_manifest_sha256 = (
                self._service.multipart_manifest_sha256(parts)
                if candidate.upload_mode == "multipart"
                else None
            )
        self._assert_storage_profile(
            gateway=gateway, storage_profile=candidate.storage_profile
        )
        if candidate.upload_mode == "multipart" and candidate.status == "uploading":
            object_head = await gateway.complete_multipart_upload(
                object_key=candidate.object_key,
                upload_session_ref=str(candidate.upload_session_ref),
                parts=parts,
            )
        else:
            object_head = await gateway.head_object(object_key=candidate.object_key)
        async with self._service.db.begin():
            return await self._service.accept_upload_complete(
                image_id=candidate.image_id,
                requester_id=requester_id,
                expected_state_version=payload.expected_state_version,
                object_head=object_head,
                trace_id=payload.trace_id,
                multipart_manifest_sha256=multipart_manifest_sha256,
            )

    async def abort_upload(
        self,
        *,
        payload: ImageAbortCommand,
        requester_id: str,
        gateway_factory: GatewayFactory,
    ) -> ImageResponse:
        async with self._service.db.begin():
            candidate = await self._service.get_upload_operation_candidate(
                image_id=payload.id,
                requester_id=requester_id,
                expected_state_version=payload.expected_state_version,
                generation=payload.generation,
                operation="abort",
            )
        if candidate.upload_mode == "multipart" and candidate.upload_session_ref:
            gateway = gateway_factory()
            self._assert_storage_profile(
                gateway=gateway, storage_profile=candidate.storage_profile
            )
            await gateway.abort_multipart_upload(
                object_key=candidate.object_key,
                upload_session_ref=candidate.upload_session_ref,
            )
        async with self._service.db.begin():
            return await self._service.abort_upload(
                image_id=payload.id,
                requester_id=requester_id,
                expected_state_version=payload.expected_state_version,
                generation=payload.generation,
            )


__all__ = ["ImageUploadWorkflow"]
