from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.config import settings
from apps.backend.core.contexts import CallerContext
from apps.backend.core.dependencies import (
    get_async_session,
    get_explicit_transaction_session,
    require_caller_scope,
)
from apps.backend.schemas.base import GenericResponse
from apps.backend.schemas.task import TaskCreate, TaskResponse
from apps.backend.schemas.xray_quality import (
    XRayQualityReviewCreate,
    XRayQualityReviewResponse,
)
from apps.backend.services.runtime.api.api_v1.endpoints.imaging_errors import (
    rollback_and_map,
)
from apps.backend.services.runtime.service.task_service import TaskService

router = APIRouter(
    prefix="/xray-quality-reviews",
    tags=["X-Ray quality reviews"],
)
caller = require_caller_scope(settings.IMAGING_REQUIRED_SCOPE)


async def get_task_service(
    db: AsyncSession = Depends(get_async_session),
) -> TaskService:
    return TaskService(db)


async def get_task_write_service(
    db: AsyncSession = Depends(get_explicit_transaction_session),
) -> TaskService:
    return TaskService(db)


@router.post(
    "",
    response_model=GenericResponse[TaskResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_xray_quality_review(
    payload: XRayQualityReviewCreate,
    context: CallerContext = Depends(caller),
    service: TaskService = Depends(get_task_write_service),
    db: AsyncSession = Depends(get_explicit_transaction_session),
):
    try:
        async with db.begin():
            data = await service.create_task(
                payload=TaskCreate(
                    study_id=payload.study_id,
                    study_revision_id=payload.study_revision_id,
                    request_id=payload.request_id,
                    task_type="xray_quality_control",
                    species=payload.species,
                    trace_id=payload.trace_id,
                ),
                caller=context,
            )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="X-Ray 图片部位识别任务已受理", data=data)


@router.get("", response_model=GenericResponse[XRayQualityReviewResponse])
async def get_xray_quality_review(
    task_id: str = Query(..., min_length=1, max_length=64),
    context: CallerContext = Depends(caller),
    service: TaskService = Depends(get_task_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_xray_quality_review(
            task_id=task_id,
            caller=context,
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="X-Ray 图片部位识别结果查询成功", data=data)


__all__ = ["router"]
