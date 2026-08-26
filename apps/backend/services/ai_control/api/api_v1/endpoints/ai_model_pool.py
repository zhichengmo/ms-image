"""Model pool source control-plane endpoints."""

from math import ceil

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.contexts import ControlPlaneContext
from apps.backend.core.dependencies import get_async_session, require_control_plane_scope
from apps.backend.schemas.ai_control import (
    ModelPoolCreate,
    ModelPoolResponse,
    ModelPoolUpdate,
    PageResult,
    RetireCommandRequest,
    StateCommandRequest,
)
from apps.backend.schemas.base import GenericResponse, PageInfo, PagedResponse
from apps.backend.services.ai_control.errors import rollback_and_map_control_plane
from apps.backend.services.ai_control.service.model_pool_service import ModelPoolService

router = APIRouter(prefix="/ai-model-pools", tags=["AI Model Pool ControlPlane"])
control = require_control_plane_scope()


async def get_service(
    db: AsyncSession = Depends(get_async_session),
) -> ModelPoolService:
    return ModelPoolService(db)


def _paged(result: PageResult[ModelPoolResponse], message: str) -> PagedResponse[ModelPoolResponse]:
    return PagedResponse(
        message=message,
        data=result.data,
        page_info=PageInfo(
            total=result.total,
            page=result.page,
            limit=result.limit,
            total_pages=ceil(result.total / result.limit) if result.total else 0,
        ),
    )


@router.post("", response_model=GenericResponse[ModelPoolResponse], status_code=status.HTTP_201_CREATED)
async def create_model_pool(
    payload: ModelPoolCreate,
    context: ControlPlaneContext = Depends(control),
    service: ModelPoolService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.create(payload=payload, actor=context)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Model Pool 已创建", data=data)


@router.put("", response_model=GenericResponse[ModelPoolResponse])
async def update_model_pool(
    payload: ModelPoolUpdate,
    context: ControlPlaneContext = Depends(control),
    service: ModelPoolService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.update(payload=payload, actor=context)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Model Pool 已更新", data=data)


@router.get("/detail", response_model=GenericResponse[ModelPoolResponse])
async def get_model_pool_detail(
    pool_id: str = Query(..., alias="id", min_length=1, max_length=64),
    _: ControlPlaneContext = Depends(control),
    service: ModelPoolService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.detail(pool_id=pool_id)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Model Pool 查询成功", data=data)


@router.get("/page", response_model=PagedResponse[ModelPoolResponse])
async def page_model_pools(
    execution_mode: str | None = Query(default=None, max_length=32),
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: ControlPlaneContext = Depends(control),
    service: ModelPoolService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        result = await service.page(
            page=page,
            limit=page_size,
            execution_mode=execution_mode,
            status=status_filter,
        )
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return _paged(result, "AI Model Pool 分页查询成功")


@router.post("/validate", response_model=GenericResponse[ModelPoolResponse])
async def validate_model_pool(
    payload: StateCommandRequest,
    context: ControlPlaneContext = Depends(control),
    service: ModelPoolService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.validate(payload=payload, actor=context)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Model Pool 已验证", data=data)


@router.post("/retire", response_model=GenericResponse[ModelPoolResponse])
async def retire_model_pool(
    payload: RetireCommandRequest,
    context: ControlPlaneContext = Depends(control),
    service: ModelPoolService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.retire(payload=payload, actor=context)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Model Pool 已退役", data=data)


__all__ = ["router"]
