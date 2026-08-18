from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.api_v1.endpoints.imaging_errors import rollback_and_map
from app.api.deps import get_async_session, get_image_service, require_resource_scope
from app.core.config import settings
from app.schemas.base import GenericResponse
from app.schemas.image import ImageAbortCommand, ImageResponse
from app.service.image_service import ImageService


router = APIRouter(prefix="/images", tags=["Imaging images"])
resource_context = require_resource_scope(settings.IMAGING_REQUIRED_SCOPE)


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
