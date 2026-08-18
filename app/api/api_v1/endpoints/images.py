from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.api_v1.endpoints.imaging_errors import rollback_and_map
from app.api.deps import (
    ImageStorageDependencies,
    get_async_session,
    get_image_service,
    get_image_storage_dependencies,
    require_resource_scope,
)
from app.core.config import settings
from app.core.imaging.object_store import ObjectStoreError
from app.schemas.base import GenericResponse
from app.schemas.image import (
    ImageAbortCommand,
    ImagePrepareUploadRequest,
    ImageResponse,
    ImageUploadTicket,
)
from app.service.image_service import ImageService


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
    service: ImageService = Depends(get_image_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.abort_upload(
            image_id=payload.id,
            requester_id=context["subject"],
            expected_state_version=payload.expected_state_version,
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Image 上传已终止", data=data)


__all__ = ["router"]
