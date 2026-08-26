"""Immutable Config v2 control-plane endpoints (API -> Service only)."""

from __future__ import annotations

from math import ceil

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.core.contexts import ControlPlaneContext
from apps.backend.core.dependencies import get_async_session, require_control_plane_scope
from apps.backend.schemas.ai_config import (
    AIConfigActivateRequest,
    AIConfigCompilePreview,
    AIConfigCreate,
    AIConfigResponse,
    AIConfigRollbackRequest,
    AIConfigStateRequest,
)
from apps.backend.schemas.ai_control import PageResult, RetireCommandRequest
from apps.backend.schemas.base import GenericResponse, PageInfo, PagedResponse
from apps.backend.services.ai_control.errors import rollback_and_map_control_plane
from apps.backend.services.ai_control.service.ai_config_service import AIConfigService

router = APIRouter(prefix="/ai-configs", tags=["AI Config ControlPlane"])
control = require_control_plane_scope()


async def get_service(
    db: AsyncSession = Depends(get_async_session),
) -> AIConfigService:
    return AIConfigService(db)


def _paged(result: PageResult[AIConfigResponse]) -> PagedResponse[AIConfigResponse]:
    return PagedResponse(
        message="AI Config 分页查询成功",
        data=result.data,
        page_info=PageInfo(
            total=result.total,
            page=result.page,
            limit=result.limit,
            total_pages=ceil(result.total / result.limit) if result.total else 0,
        ),
    )


@router.post(
    "/compile-preview",
    response_model=GenericResponse[AIConfigCompilePreview],
)
async def compile_preview(
    payload: AIConfigCreate,
    _: ControlPlaneContext = Depends(control),
    service: AIConfigService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.compile_preview(payload=payload)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Config 编译预览成功", data=data)


@router.post(
    "",
    response_model=GenericResponse[AIConfigResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create(
    payload: AIConfigCreate,
    context: ControlPlaneContext = Depends(control),
    service: AIConfigService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.create(payload=payload, actor=context)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Config 已创建", data=data)


@router.get("/detail", response_model=GenericResponse[AIConfigResponse])
async def detail(
    config_id: str = Query(..., alias="id", min_length=1, max_length=64),
    _: ControlPlaneContext = Depends(control),
    service: AIConfigService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.detail(config_id=config_id)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Config 详情查询成功", data=data)


@router.get("/page", response_model=PagedResponse[AIConfigResponse])
async def page(
    config_key: str | None = Query(default=None, min_length=1, max_length=128),
    status_filter: str | None = Query(default=None, alias="status", min_length=1, max_length=32),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: ControlPlaneContext = Depends(control),
    service: AIConfigService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        result = await service.page(
            page=page,
            limit=page_size,
            config_key=config_key,
            status=status_filter,
        )
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return _paged(result)


@router.get("/active", response_model=GenericResponse[AIConfigResponse])
async def get_active(
    config_key: str = Query(..., min_length=1, max_length=128),
    modality_type: str = Query(..., min_length=1, max_length=32),
    task_type: str = Query(..., min_length=1, max_length=48),
    activation_scope: str = Query(default="global", min_length=1, max_length=32),
    scope_key: str = Query(default="global", min_length=1, max_length=128),
    _: ControlPlaneContext = Depends(control),
    service: AIConfigService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.get_active(
            config_key=config_key,
            modality_type=modality_type,
            task_type=task_type,
            activation_scope=activation_scope,
            scope_key=scope_key,
        )
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="Active AI Config 查询成功", data=data)


@router.post("/validate", response_model=GenericResponse[AIConfigResponse])
async def validate(
    payload: AIConfigStateRequest,
    context: ControlPlaneContext = Depends(control),
    service: AIConfigService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.validate(payload=payload, actor=context)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Config 已验证", data=data)


@router.post("/activate", response_model=GenericResponse[AIConfigResponse])
async def activate(
    payload: AIConfigActivateRequest,
    context: ControlPlaneContext = Depends(control),
    service: AIConfigService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.activate(payload=payload, actor=context)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Config 已激活", data=data)


@router.post("/retire", response_model=GenericResponse[AIConfigResponse])
async def retire(
    payload: RetireCommandRequest,
    context: ControlPlaneContext = Depends(control),
    service: AIConfigService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.retire(payload=payload, actor=context)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Config 已退役", data=data)


@router.post("/rollback", response_model=GenericResponse[AIConfigResponse])
async def rollback(
    payload: AIConfigRollbackRequest,
    context: ControlPlaneContext = Depends(control),
    service: AIConfigService = Depends(get_service),
    db: AsyncSession = Depends(get_async_session),
):
    try:
        data = await service.rollback(payload=payload, actor=context)
    except Exception as exc:
        return await rollback_and_map_control_plane(db, exc)
    return GenericResponse(message="AI Config 回滚成功", data=data)


__all__ = ["router"]
