from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.config import settings
from apps.backend.core.contexts import CallerContext
from apps.backend.core.dependencies import get_async_session, require_caller_scope
from apps.backend.schemas.anatomy_localization import AnatomyLocalizationResponse
from apps.backend.schemas.base import GenericResponse
from apps.backend.services.runtime.api.api_v1.endpoints.imaging_errors import (
    rollback_and_map,
)
from apps.backend.services.runtime.service.task_service import TaskService

router = APIRouter(
    prefix="/anatomy-localizations",
    tags=["Anatomy localizations"],
)
caller = require_caller_scope(settings.IMAGING_REQUIRED_SCOPE)


async def get_task_service(
    db: AsyncSession = Depends(get_async_session),
) -> TaskService:
    return TaskService(db)


@router.get("", response_model=GenericResponse[AnatomyLocalizationResponse])
async def get_anatomy_localization(
    task_id: str = Query(..., min_length=1, max_length=64),
    context: CallerContext = Depends(caller),
    service: TaskService = Depends(get_task_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_anatomy_localization(
            task_id=task_id,
            caller=context,
        )
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="器官定位结果查询成功", data=data)


__all__ = ["router"]
