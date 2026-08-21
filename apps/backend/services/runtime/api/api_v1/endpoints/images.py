from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.services.runtime.api.api_v1.endpoints.imaging_errors import rollback_and_map
from apps.backend.core.dependencies import (
    ImageStorageDependencies,
    get_async_session,
    get_image_service,
    get_image_storage_dependencies,
    require_resource_scope,
)
from apps.backend.core.config import settings
from apps.backend.core.imaging.object_store import ObjectStoreError
from apps.backend.schemas.base import GenericResponse
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
    ImageReplaceRequest,
    ImageReplaceMultipartRequest,
    ImageResponse,
    ImageSignedPart,
    ImageUploadTicket,
)
from apps.backend.services.runtime.service.image_service import ImageService


router = APIRouter(prefix="/images", tags=["Imaging images"])
resource_context = require_resource_scope(settings.IMAGING_REQUIRED_SCOPE)


@router.post(
    "/prepare-upload",
    response_model=GenericResponse[ImageUploadTicket],
    status_code=status.HTTP_201_CREATED,
)
async def prepare_upload(
    payload: ImagePrepareUploadRequest,
    context: dict = Depends(resource_context),
    dependencies: ImageStorageDependencies = Depends(get_image_storage_dependencies),
):
    try:
        gateway = dependencies.gateway_factory()
        ttl_seconds = int(settings.OSS_SIGNED_URL_TTL_SECONDS)
        if ttl_seconds < 1:
            raise ObjectStoreError("object_signed_url_ttl_invalid")
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        async with dependencies.db.begin():
            image = await dependencies.service.prepare_direct_upload(
                payload=payload,
                requester_id=context["subject"],
                storage_profile=gateway.storage_profile,
                upload_expires_at=expires_at,
            )
        grant = await gateway.prepare_direct_upload(
            object_key=image.object_key,
            content_type=payload.declared_content_type,
            expires_seconds=ttl_seconds,
        )
        if (
            grant.storage_profile != image.storage_profile
            or grant.object_key != image.object_key
            or grant.upload_mode != "direct_put"
        ):
            raise ObjectStoreError("object_upload_grant_identity_conflict")
        data = ImageUploadTicket(
            image=image,
            generation=image.image_version_no,
            upload_mode=grant.upload_mode,
            required_headers=grant.required_headers,
            expires_at=expires_at,
            signed_url=grant.signed_url,
        )
    except Exception as exc:
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 上传已准备", data=data)


@router.post(
    "/replace",
    response_model=GenericResponse[ImageUploadTicket],
    status_code=status.HTTP_201_CREATED,
)
async def replace_image(
    payload: ImageReplaceRequest,
    context: dict = Depends(resource_context),
    dependencies: ImageStorageDependencies = Depends(get_image_storage_dependencies),
):
    try:
        gateway = dependencies.gateway_factory()
        ttl_seconds = int(settings.OSS_SIGNED_URL_TTL_SECONDS)
        if ttl_seconds < 1:
            raise ObjectStoreError("object_signed_url_ttl_invalid")
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        async with dependencies.db.begin():
            image = await dependencies.service.prepare_direct_replacement(
                payload=payload,
                requester_id=context["subject"],
                storage_profile=gateway.storage_profile,
                upload_expires_at=expires_at,
            )
        grant = await gateway.prepare_direct_upload(
            object_key=image.object_key,
            content_type=payload.declared_content_type,
            expires_seconds=ttl_seconds,
        )
        if grant.object_key != image.object_key or grant.upload_mode != "direct_put":
            raise ObjectStoreError("object_upload_grant_identity_conflict")
        data = ImageUploadTicket(
            image=image,
            generation=image.image_version_no,
            upload_mode="direct_put",
            required_headers=grant.required_headers,
            expires_at=expires_at,
            signed_url=grant.signed_url,
        )
    except Exception as exc:
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 替换上传已准备", data=data)


@router.post(
    "/replace-multipart",
    response_model=GenericResponse[ImageMultipartUploadTicket],
    status_code=status.HTTP_201_CREATED,
)
async def replace_image_multipart(
    payload: ImageReplaceMultipartRequest,
    context: dict = Depends(resource_context),
    dependencies: ImageStorageDependencies = Depends(get_image_storage_dependencies),
):
    gateway = None
    grant = None
    created_session = False
    try:
        gateway = dependencies.gateway_factory()
        ttl_seconds = int(settings.OSS_SIGNED_URL_TTL_SECONDS)
        if ttl_seconds < 1:
            raise ObjectStoreError("object_signed_url_ttl_invalid")
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        async with dependencies.db.begin():
            image = await dependencies.service.prepare_multipart_replacement(
                payload=payload,
                requester_id=context["subject"],
                storage_profile=gateway.storage_profile,
                upload_expires_at=expires_at,
            )
            candidate = await dependencies.service.get_upload_operation_candidate(
                image_id=image.id,
                requester_id=context["subject"],
                expected_state_version=image.state_version,
                generation=image.image_version_no,
                operation="multipart_prepare",
            )
        if candidate.upload_session_ref:
            upload_session_ref = candidate.upload_session_ref
            headers = {"Content-Type": payload.declared_content_type}
        else:
            grant = await gateway.initiate_multipart_upload(
                object_key=image.object_key,
                content_type=payload.declared_content_type,
                expires_seconds=ttl_seconds,
            )
            if not grant.upload_session_ref:
                raise ObjectStoreError("multipart_upload_session_missing")
            created_session = True
            upload_session_ref = grant.upload_session_ref
            headers = grant.required_headers
            async with dependencies.db.begin():
                image = await dependencies.service.bind_multipart_upload_session(
                    image_id=image.id,
                    requester_id=context["subject"],
                    expected_state_version=image.state_version,
                    generation=image.image_version_no,
                    upload_session_ref=upload_session_ref,
                    upload_expires_at=expires_at,
                )
        data = ImageMultipartUploadTicket(
            image=image,
            generation=image.image_version_no,
            upload_mode="multipart",
            required_headers=headers,
            expires_at=expires_at,
            upload_session_ref=upload_session_ref,
        )
    except Exception as exc:
        if created_session and gateway is not None and grant is not None:
            try:
                await gateway.abort_multipart_upload(
                    object_key=grant.object_key,
                    upload_session_ref=str(grant.upload_session_ref),
                )
            except Exception:
                pass
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 分片替换上传已准备", data=data)


@router.post(
    "/prepare-multipart-upload",
    response_model=GenericResponse[ImageMultipartUploadTicket],
    status_code=status.HTTP_201_CREATED,
)
async def prepare_multipart_upload(
    payload: ImagePrepareMultipartRequest,
    context: dict = Depends(resource_context),
    dependencies: ImageStorageDependencies = Depends(get_image_storage_dependencies),
):
    gateway = None
    grant = None
    created_session = False
    try:
        gateway = dependencies.gateway_factory()
        ttl_seconds = int(settings.OSS_SIGNED_URL_TTL_SECONDS)
        if ttl_seconds < 1:
            raise ObjectStoreError("object_signed_url_ttl_invalid")
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        async with dependencies.db.begin():
            image = await dependencies.service.prepare_multipart_upload(
                payload=payload,
                requester_id=context["subject"],
                storage_profile=gateway.storage_profile,
                upload_expires_at=expires_at,
            )
            candidate = await dependencies.service.get_upload_operation_candidate(
                image_id=image.id,
                requester_id=context["subject"],
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
            if not grant.upload_session_ref:
                raise ObjectStoreError("multipart_upload_session_missing")
            created_session = True
            upload_session_ref = grant.upload_session_ref
            required_headers = grant.required_headers
            async with dependencies.db.begin():
                image = await dependencies.service.bind_multipart_upload_session(
                    image_id=image.id,
                    requester_id=context["subject"],
                    expected_state_version=image.state_version,
                    generation=image.image_version_no,
                    upload_session_ref=upload_session_ref,
                    upload_expires_at=expires_at,
                )
        data = ImageMultipartUploadTicket(
            image=image,
            generation=image.image_version_no,
            upload_mode="multipart",
            required_headers=required_headers,
            expires_at=expires_at,
            upload_session_ref=upload_session_ref,
        )
    except Exception as exc:
        if created_session and gateway is not None and grant is not None:
            try:
                await gateway.abort_multipart_upload(
                    object_key=grant.object_key,
                    upload_session_ref=str(grant.upload_session_ref),
                )
            except Exception:
                pass
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 分片上传已准备", data=data)


@router.post(
    "/prepare-upload-parts",
    response_model=GenericResponse[ImageMultipartPartsResponse],
)
async def prepare_upload_parts(
    payload: ImagePreparePartsRequest,
    context: dict = Depends(resource_context),
    dependencies: ImageStorageDependencies = Depends(get_image_storage_dependencies),
):
    try:
        gateway = dependencies.gateway_factory()
        async with dependencies.db.begin():
            candidate = await dependencies.service.get_upload_operation_candidate(
                image_id=payload.id,
                requester_id=context["subject"],
                expected_state_version=payload.expected_state_version,
                generation=payload.generation,
                operation="parts",
            )
            part_numbers = dependencies.service.validate_multipart_part_numbers(
                candidate, payload.part_numbers
            )
        if gateway.storage_profile != candidate.storage_profile:
            raise ObjectStoreError("object_storage_profile_mismatch")
        signed = await gateway.sign_multipart_parts(
            object_key=candidate.object_key,
            upload_session_ref=str(candidate.upload_session_ref),
            part_numbers=part_numbers,
        )
        data = ImageMultipartPartsResponse(
            id=candidate.image_id,
            generation=candidate.generation,
            parts=[
                ImageSignedPart(part_number=number, signed_url=signed[number])
                for number in part_numbers
            ],
        )
    except Exception as exc:
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 分片上传地址已准备", data=data)


@router.post(
    "/list-upload-parts",
    response_model=GenericResponse[list[ImageMultipartPartReceipt]],
)
async def list_upload_parts(
    payload: ImageListMultipartPartsRequest,
    context: dict = Depends(resource_context),
    dependencies: ImageStorageDependencies = Depends(get_image_storage_dependencies),
):
    try:
        gateway = dependencies.gateway_factory()
        async with dependencies.db.begin():
            candidate = await dependencies.service.get_upload_operation_candidate(
                image_id=payload.id,
                requester_id=context["subject"],
                expected_state_version=payload.expected_state_version,
                generation=payload.generation,
                operation="list_parts",
            )
        if gateway.storage_profile != candidate.storage_profile:
            raise ObjectStoreError("object_storage_profile_mismatch")
        parts = await gateway.list_multipart_parts(
            object_key=candidate.object_key,
            upload_session_ref=str(candidate.upload_session_ref),
        )
        data = [
            ImageMultipartPartReceipt(
                part_number=item.part_number,
                etag=item.etag,
                size_bytes=item.size_bytes,
            )
            for item in parts
        ]
    except Exception as exc:
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 已上传分片查询成功", data=data)


@router.post(
    "/complete-upload",
    response_model=GenericResponse[ImageResponse],
)
async def complete_upload(
    payload: ImageCompleteUploadRequest,
    context: dict = Depends(resource_context),
    dependencies: ImageStorageDependencies = Depends(get_image_storage_dependencies),
):
    try:
        gateway = dependencies.gateway_factory()
        async with dependencies.db.begin():
            candidate = await dependencies.service.get_upload_operation_candidate(
                image_id=payload.id,
                requester_id=context["subject"],
                expected_state_version=payload.expected_state_version,
                generation=payload.generation,
                operation="complete",
            )
            parts = dependencies.service.build_multipart_completion_parts(
                candidate, payload.parts
            )
            multipart_manifest_sha256 = (
                dependencies.service.multipart_manifest_sha256(parts)
                if candidate.upload_mode == "multipart"
                else None
            )
        if gateway.storage_profile != candidate.storage_profile:
            raise ObjectStoreError("object_storage_profile_mismatch")
        if candidate.upload_mode == "multipart" and candidate.status == "uploading":
            head = await gateway.complete_multipart_upload(
                object_key=candidate.object_key,
                upload_session_ref=str(candidate.upload_session_ref),
                parts=parts,
            )
        else:
            head = await gateway.head_object(object_key=candidate.object_key)
        async with dependencies.db.begin():
            data = await dependencies.service.accept_upload_complete(
                image_id=candidate.image_id,
                requester_id=context["subject"],
                expected_state_version=payload.expected_state_version,
                object_head=head,
                trace_id=payload.trace_id,
                multipart_manifest_sha256=multipart_manifest_sha256,
            )
    except Exception as exc:
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 上传完成，已进入校验", data=data)


@router.get("", response_model=GenericResponse[ImageResponse])
async def get_image(
    image_id: str = Query(..., alias="id", min_length=1, max_length=64),
    context: dict = Depends(resource_context),
    service: ImageService = Depends(get_image_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_image(image_id=image_id, requester_id=context["subject"])
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Image 查询成功", data=data)


@router.post("/abort-upload", response_model=GenericResponse[ImageResponse])
async def abort_upload(
    payload: ImageAbortCommand,
    context: dict = Depends(resource_context),
    dependencies: ImageStorageDependencies = Depends(get_image_storage_dependencies),
):
    try:
        async with dependencies.db.begin():
            candidate = await dependencies.service.get_upload_operation_candidate(
                image_id=payload.id,
                requester_id=context["subject"],
                expected_state_version=payload.expected_state_version,
                generation=payload.generation,
                operation="abort",
            )
        if candidate.upload_mode == "multipart" and candidate.upload_session_ref:
            gateway = dependencies.gateway_factory()
            if gateway.storage_profile != candidate.storage_profile:
                raise ObjectStoreError("object_storage_profile_mismatch")
            await gateway.abort_multipart_upload(
                object_key=candidate.object_key,
                upload_session_ref=candidate.upload_session_ref,
            )
        async with dependencies.db.begin():
            data = await dependencies.service.abort_upload(
                image_id=payload.id,
                requester_id=context["subject"],
                expected_state_version=payload.expected_state_version,
                generation=payload.generation,
            )
    except Exception as exc:
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 上传已终止", data=data)


__all__ = ["router"]
