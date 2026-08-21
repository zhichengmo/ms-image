from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.services.runtime.api.api_v1.endpoints.imaging_errors import rollback_and_map
from apps.backend.core.dependencies import get_async_session, get_study_service, require_resource_scope
from apps.backend.core.config import settings
from apps.backend.schemas.base import GenericResponse
from apps.backend.schemas.study import (
    SeriesCreate,
    SeriesResponse,
    StudyCreate,
    StudyDetailResponse,
    StudyFinalizeRequest,
    StudyResponse,
)
from apps.backend.services.runtime.service.study_service import StudyService


router = APIRouter(tags=["Imaging studies"])
resource_context = require_resource_scope(settings.IMAGING_REQUIRED_SCOPE)


@router.post("/studies", response_model=GenericResponse[StudyResponse], status_code=status.HTTP_201_CREATED)
async def create_study(
    payload: StudyCreate,
    context: dict = Depends(resource_context),
    service: StudyService = Depends(get_study_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.create_study(payload=payload, requester_id=context["subject"])
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Study 已创建", data=data)


@router.get("/studies", response_model=GenericResponse[StudyDetailResponse])
async def get_study(
    study_id: str = Query(..., alias="id", min_length=1, max_length=64),
    context: dict = Depends(resource_context),
    service: StudyService = Depends(get_study_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_study(study_id=study_id, requester_id=context["subject"])
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Study 查询成功", data=data)


@router.post("/studies/finalize", response_model=GenericResponse[StudyResponse])
async def finalize_study(
    payload: StudyFinalizeRequest,
    context: dict = Depends(resource_context),
    service: StudyService = Depends(get_study_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.finalize_study(
            payload=payload, requester_id=context["subject"]
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Study 已完成", data=data)


@router.post("/series", response_model=GenericResponse[SeriesResponse], status_code=status.HTTP_201_CREATED)
async def create_series(
    payload: SeriesCreate,
    context: dict = Depends(resource_context),
    service: StudyService = Depends(get_study_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.create_series(payload=payload, requester_id=context["subject"])
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Series 已创建", data=data)


__all__ = ["router"]
