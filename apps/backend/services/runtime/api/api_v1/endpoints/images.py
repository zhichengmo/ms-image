from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.config import settings
from apps.backend.core.dependencies import (
    ImageStorageDependencies,
    get_async_session,
    get_image_service,
    get_image_storage_dependencies,
    require_resource_scope,
)
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
    ImageReplaceMultipartRequest,
    ImageReplaceRequest,
    ImageResponse,
    ImageUploadTicket,
)
from apps.backend.services.runtime.api.api_v1.endpoints.imaging_errors import (
    rollback_and_map,
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
        data = await dependencies.service.issue_direct_upload(
            payload=payload,
            requester_id=context["subject"],
            gateway_factory=dependencies.gateway_factory,
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
        data = await dependencies.service.issue_direct_replacement(
            payload=payload,
            requester_id=context["subject"],
            gateway_factory=dependencies.gateway_factory,
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
    try:
        data = await dependencies.service.issue_multipart_replacement(
            payload=payload,
            requester_id=context["subject"],
            gateway_factory=dependencies.gateway_factory,
        )
    except Exception as exc:
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
    try:
        data = await dependencies.service.issue_multipart_upload(
            payload=payload,
            requester_id=context["subject"],
            gateway_factory=dependencies.gateway_factory,
        )
    except Exception as exc:
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
        data = await dependencies.service.issue_multipart_part_urls(
            payload=payload,
            requester_id=context["subject"],
            gateway_factory=dependencies.gateway_factory,
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
        data = await dependencies.service.list_multipart_parts(
            payload=payload,
            requester_id=context["subject"],
            gateway_factory=dependencies.gateway_factory,
        )
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
        data = await dependencies.service.complete_upload_workflow(
            payload=payload,
            requester_id=context["subject"],
            gateway_factory=dependencies.gateway_factory,
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
        data = await dependencies.service.abort_upload_workflow(
            payload=payload,
            requester_id=context["subject"],
            gateway_factory=dependencies.gateway_factory,
        )
    except Exception as exc:
        return await rollback_and_map(dependencies.db, exc)
    return GenericResponse(message="Image 上传已终止", data=data)


__all__ = ["router"]
