from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.services.runtime.api.api_v1.endpoints.imaging_errors import rollback_and_map
from apps.backend.core.dependencies import get_async_session, require_caller_scope
from apps.backend.core.config import settings
from apps.backend.core.contexts import CallerContext
from apps.backend.schemas.base import GenericResponse, PageInfo, PagedResponse
from apps.backend.schemas.task import (
    TaskCancelRequest,
    TaskCreate,
    TaskPageQuery,
    TaskResponse,
    TaskStatusResponse,
)
from apps.backend.services.runtime.service.task_service import TaskService

router = APIRouter(prefix="/tasks", tags=["Imaging tasks"])
caller = require_caller_scope(settings.IMAGING_REQUIRED_SCOPE)

async def get_task_service(db: AsyncSession = Depends(get_async_session)) -> TaskService:
    return TaskService(db)

@router.post("", response_model=GenericResponse[TaskResponse], status_code=status.HTTP_201_CREATED)
async def create_task(payload: TaskCreate, context: CallerContext = Depends(caller), service: TaskService = Depends(get_task_service), db: AsyncSession = Depends(get_async_session)):
    try:
        data = await service.create_task(payload=payload, caller=context)
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Task 已受理", data=data)

@router.get("", response_model=GenericResponse[TaskResponse])
async def get_task(task_id: str = Query(..., alias="id", min_length=1, max_length=64), context: CallerContext = Depends(caller), service: TaskService = Depends(get_task_service), db: AsyncSession = Depends(get_async_session)):
    try:
        data = await service.get_task(task_id=task_id, caller=context)
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Task 查询成功", data=data)


@router.get("/page", response_model=PagedResponse[TaskStatusResponse])
async def page_tasks(
    query: Annotated[TaskPageQuery, Query()],
    context: CallerContext = Depends(caller),
    service: TaskService = Depends(get_task_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        result = await service.page_tasks(query=query, caller=context)
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return PagedResponse(
        message="Task 分页查询成功",
        data=result.data,
        page_info=PageInfo(
            total=result.total,
            page=result.page,
            limit=result.limit,
            total_pages=ceil(result.total / result.limit) if result.total else 0,
        ),
    )


@router.post("/cancel", response_model=GenericResponse[TaskResponse])
async def cancel_task(payload: TaskCancelRequest, context: CallerContext = Depends(caller), service: TaskService = Depends(get_task_service), db: AsyncSession = Depends(get_async_session)):
    try:
        data = await service.cancel_task(task_id=payload.id, expected_version=payload.expected_state_version, reason=payload.reason, caller=context)
    except Exception as exc:
        return await rollback_and_map(db, exc)
    return GenericResponse(message="Task 取消请求已记录", data=data)
