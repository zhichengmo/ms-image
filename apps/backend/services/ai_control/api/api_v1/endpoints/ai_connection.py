"""Connection source control-plane endpoints with redacted Secret references."""

from math import ceil

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.contexts import ControlPlaneContext
from apps.backend.core.dependencies import get_async_session, require_control_plane_scope
from apps.backend.schemas.ai_control import (
    ConnectionCreate,
    ConnectionResponse,
    ConnectionUpdate,
    PageResult,
    RetireCommandRequest,
    StateCommandRequest,
)
from apps.backend.schemas.base import GenericResponse, PageInfo, PagedResponse
from apps.backend.services.ai_control.errors import rollback_and_map_control_plane
from apps.backend.services.ai_control.service.api_connection_service import APIConnectionService

router = APIRouter(prefix="/ai-connections", tags=["AI Connection ControlPlane"])
control = require_control_plane_scope()


async def get_service(
    db: AsyncSession = Depends(get_async_session),
) -> APIConnectionService:
    return APIConnectionService(db)


def _paged(result: PageResult[ConnectionResponse], message: str) -> PagedResponse[ConnectionResponse]:
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


@router.post("", response_model=GenericResponse[ConnectionResponse], status_code=status.HTTP_201_CREATED)
async def create_connection(
    payload: ConnectionCreate,
    context: ControlPlaneContext = Depends(control),
    service: APIConnectionService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.create(payload=payload, actor=context)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Connection 已创建", data=data)


@router.put("", response_model=GenericResponse[ConnectionResponse])
async def update_connection(
    payload: ConnectionUpdate,
    context: ControlPlaneContext = Depends(control),
    service: APIConnectionService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.update(payload=payload, actor=context)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Connection 已更新", data=data)


@router.get("/detail", response_model=GenericResponse[ConnectionResponse])
async def get_connection_detail(
    connection_id: str = Query(..., alias="id", min_length=1, max_length=64),
    _: ControlPlaneContext = Depends(control),
    service: APIConnectionService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.detail(connection_id=connection_id)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Connection 查询成功", data=data)


@router.get("/page", response_model=PagedResponse[ConnectionResponse])
async def page_connections(
    provider_type: str | None = Query(default=None, max_length=64),
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: ControlPlaneContext = Depends(control),
    service: APIConnectionService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        result = await service.page(
            page=page,
            limit=page_size,
            provider_type=provider_type,
            status=status_filter,
        )
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return _paged(result, "AI Connection 分页查询成功")


@router.post("/validate", response_model=GenericResponse[ConnectionResponse])
async def validate_connection(
    payload: StateCommandRequest,
    context: ControlPlaneContext = Depends(control),
    service: APIConnectionService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.validate(payload=payload, actor=context)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Connection 已验证", data=data)


@router.post("/retire", response_model=GenericResponse[ConnectionResponse])
async def retire_connection(
    payload: RetireCommandRequest,
    context: ControlPlaneContext = Depends(control),
    service: APIConnectionService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.retire(payload=payload, actor=context)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Connection 已退役", data=data)


__all__ = ["router"]
